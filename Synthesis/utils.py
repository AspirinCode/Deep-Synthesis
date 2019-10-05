import streamlit as st 
import os
from rdkit import Chem
from rdkit.Chem import Draw
import logging
import time

from preprocess import *
from postprocess import *
from confirm_button import *

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def app_setup():
    # starter values for prediction type 
    input_options = ['Predict from String', 'Predict from File']

    return input_options

def get_data_params(input_options, prediction_options):
    # function determines if prediction will be run on a string input by the user
    # or from a file of SMILES strings
    if prediction_options == input_options[0]:
        single_predict = True
    else:
        single_predict = False 

    if single_predict:
        # If single predict, create a text box for user input
        base_smile = 'O=Cc1cncc(Cl)c1COC1CCCCO1.OCc1c(Cl)cncc1Cl'
        smile = st.text_input('Input Source SMILES (Required)', base_smile)
        target_smile = st.text_input('Input Target SMILES (Optional)' , '')
        # returns single_predict (bool), smile (string), target_smile (string)
        return single_predict, smile, target_smile
    else:
        # If file predict, create text boxes that let users navigate to the prediction file
        source_filename, target_filename = get_filenames()
        # returns single_predict (bool), source_filename (string to .txt filename)
        # target_filename (string to .txt filename if desired, else None)
        return single_predict, source_filename, target_filename

def get_filenames(path='data'):
    # Creates interface for user to select a file to load
    # file must be stored locally in a directory accessable from the streamlit app
    folder = st.text_input('Data Folder Path', path)
    source_filename = file_selector(folder_path=folder, txt='Select source file')

    if st.checkbox('Target File?'):
        # optional check box for a file of targets (not required)
        target_folder = st.text_input('Data Folder Path', folder)
        target_filename = file_selector(folder_path=target_folder, txt='Select target file')
    else:
        target_filename = None

    return source_filename, target_filename


def file_selector(folder_path='.', txt='Select a file'):
    # uses Streamlit string inputs to navigate to a file
    filenames = os.listdir(folder_path)
    selected_filename = st.selectbox(txt, filenames)
    return os.path.join(folder_path, selected_filename)

#@st.cache
@cache_on_button_press('Load Data')
def load_data(single_predict, source_param, target_param):
    # triggers actually loading the data
    # loaded data is cached
    if single_predict:
        # If single_predict, load with the method for a single entry
        data = SmilesData.single_entry(source_param, target_param)
    else:
        # Else, load from file
        data = SmilesData.file_entry(source_param, target_param)

    # Returns a SimlesData object
    return data 

def display_data(smile_data, display_idx):
    # displays data held in a SmilesData object
    return st.image(smile_data.display(idx=display_idx, img_size=(300,300)))

def display_slider(data):
    if len(data) > 1:
        display_idx = st.sidebar.slider('Display Index', 0, len(data)-1, 0)
    else:
        display_idx = 0
    
    return display_idx

#@st.cache(ignore_hash=True)
@cache_on_button_press('Predict Products')
def translate_data(smile_data, beam, n_best, attention, translator_class, model_description):
    # Important note: translator class must be instantiated within this function for 
    # Streamlit caching to work properly
    placeholder = st.empty()
    placeholder.text('Prediction in Progress')

    start = time.time()
    translator = translator_class(model_description)
    scores, preds, attns = translator.run_translation(smile_data.smiles_tokens, 
                                                beam=beam, n_best=n_best, return_attention=attention)
    prediction_time = time.time() - start
    prediction = Predictions(smile_data, preds, scores, attns)
    logger.info(f'Inference Time: {prediction_time}')

    placeholder.text('Prediction Complete')
    return prediction

@st.cache
def plot_topk(prediction_tokens, legend, img_size=(400,400)):
    mols = [Chem.MolFromSmiles(process_prediction(i)) for i in prediction_tokens]
    return Draw.MolsToGridImage(mols, legends=legend, subImgSize=img_size)

def display_prediction(prediction, display_idx):
    prediction_data = display_parameters(prediction, idx=display_idx)

    st.write(f'Top {prediction.top_k} Predictions')
    st.image(plot_topk([i.prediction_tokens for i in prediction_data],
                        [i.legend for i in prediction_data], img_size=(300,300)))

    if len(prediction_data) > 1:
        view_idx = st.slider('View Prediction (In Order of Model Confidence)', 0, len(prediction_data)-1, 0)
    else:
        view_idx = 0

    current_prediction = prediction_data[view_idx]
    im, attn_plot = plot_prediction(current_prediction.source_tokens,
                                    current_prediction.prediction_tokens,
                                    current_prediction.attention,
                                    current_prediction.legend,
                                    img_size=(300,300))

    st.write(f'Predicted Smile: {process_prediction(current_prediction.prediction_tokens)}')
    if im:
        st.image(im)
    st.pyplot(plt.show(attn_plot), bbox_inches = 'tight', pad_inches = 0)

    st.write('\nPrediction Dataframe')
    st.dataframe(prediction.sample_df(display_idx))

@cache_on_button_press('Save Prediction Data')
def save_data(predictions, save_folder):
    predictions.df.to_csv(save_folder, index=False)
    st.text(f'Prediction data saved to {save_folder}')

def download_data(single_predict, predictions):
    if not single_predict:
        save_folder = st.text_input('Prediction Save Destination', 'data/predictions.csv')
        save_data(predictions, save_folder)

def prediction_params(single_predict):
    if single_predict:
        beam = 5
        n_best = 5
    else:
        st.write('Input Prediction Parameters')
        beam = int(st.selectbox('Select Beam Width', [1,2,3,5]))
        n_best = int(st.selectbox('Select Top K Predictions', [1,2,3,5]))

    return beam, n_best