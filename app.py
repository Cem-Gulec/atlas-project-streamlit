import streamlit as st
import logging
import json
import time
import tempfile
import os
import plotly.graph_objects as go
import plotly.subplots as sp
import pandas as pd
import numpy as np
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
from io import BytesIO
import subprocess
import json

from home import show_home_page
from description import show_description_page
from license import show_license_page

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


# Function to set up Google Drive API client
def get_gdrive_service():
    creds = service_account.Credentials.from_service_account_file(
        'scpower-cell-atlas-ea6689019916.json',
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

# Function to fetch JSON from Google Drive
def fetch_gdrive_json(file_id):
    service = get_gdrive_service()
    try:
        file = service.files().get_media(fileId=file_id).execute()
        file_name = service.files().get(fileId=file_id, fields="name").execute().get('name')
        st.session_state.success_message.success(f"Successfully fetched *{file_name}*. Loading it...")
        time.sleep(2) 
        return json.loads(file.decode('utf-8'))
    except Exception as e:
        st.error(f"Error fetching file from Google Drive: {str(e)}")
        return None

def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        st.session_state.success_message.success("File successfully uploaded and validated as JSON...")
        time.sleep(2)
        return json.loads(content)
    except FileNotFoundError:
        st.error(f"The file '{file_path}' was not found.")
        return None
    except json.JSONDecodeError:
        st.error("The uploaded file is not valid JSON.")
        return None
    except Exception as e:
        st.error(f"An error occurred while reading the file: {str(e)}")
        return None

def create_scatter_plot(data, x_axis, y_axis, size_axis):
    df = pd.DataFrame(data)
    
    # Convert columns to numeric, replacing non-numeric values with NaN
    df[x_axis] = pd.to_numeric(df[x_axis], errors='coerce')
    df[y_axis] = pd.to_numeric(df[y_axis], errors='coerce')
    df[size_axis] = pd.to_numeric(df[size_axis], errors='coerce')
    df['Detection.power'] = pd.to_numeric(df['Detection.power'], errors='coerce')
    
    # Remove rows with NaN values
    df = df.dropna(subset=[x_axis, y_axis, size_axis, 'Detection.power'])
    
    if df.empty:
        return None
    
    # Calculate size reference
    size_ref = 2 * df[size_axis].max() / (40**2)
    
    fig = go.Figure(go.Scatter(
        x=df[x_axis],
        y=df[y_axis],
        mode='markers',
        marker=dict(
            size=df[size_axis],
            sizemode='area',
            sizeref=size_ref,
            sizemin=4,
            color=df['Detection.power'],
            colorscale='Viridis',
            colorbar=dict(title="Detection power"),
            showscale=True
        ),
        text=df.apply(lambda row: f"Sample size: {row.get('sampleSize', 'N/A')}<br>Cells per individuum: {row.get('totalCells', 'N/A')}<br>Read depth: {row.get('readDepth', 'N/A')}<br>Detection power: {row.get('Detection.power', 'N/A')}", axis=1),
        hoverinfo='text'
    ))

    fig.update_layout(
        xaxis_title=x_axis,
        yaxis_title=y_axis
    )

    return fig

def create_influence_plot(data, parameter_vector):
    df = pd.DataFrame(data)
    
    selected_pair = parameter_vector[0]
    study_type = parameter_vector[5]

    # Set grid dependent on parameter choice
    if selected_pair == "sc":
        x_axis, x_axis_label = "sampleSize", "Sample size"
        y_axis, y_axis_label = "totalCells", "Cells per sample"
    elif selected_pair == "sr":
        x_axis, x_axis_label = "sampleSize", "Sample size"
        y_axis, y_axis_label = "readDepth", "Read depth"
    else:
        x_axis, x_axis_label = "totalCells", "Cells per sample"
        y_axis, y_axis_label = "readDepth", "Read depth"

    # Check if the required columns exist
    required_columns = [x_axis, y_axis, 'sampleSize', 'totalCells', 'readDepth']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        return None

    # Select study with the maximal values 
    power_column = next((col for col in df.columns if 'power' in col.lower()), None)
    if not power_column:
        st.error("No power column found in the data.")
        return None
    max_study = df.loc[df[power_column].idxmax()]

    # Identify the columns for plotting
    plot_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['power', 'probability', 'prob'])]
    if not plot_columns:
        st.error("No suitable columns found for plotting.")
        return None

    # Create subplots
    fig = sp.make_subplots(rows=1, cols=2, shared_yaxes=True)

    # Plot cells per person
    df_plot1 = df[df[y_axis] == max_study[y_axis]]
    for col in plot_columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot1[x_axis], y=df_plot1[col],
                mode='lines+markers', name=col,
                text=[f'Sample size: {row.sampleSize}<br>Cells per individuum: {row.totalCells}<br>Read depth: {row.readDepth}<br>{col}: {row[col]:.3f}' for _, row in df_plot1.iterrows()],
                hoverinfo='text'
            ),
            row=1, col=1
        )

    # Plot read depth
    df_plot2 = df[df[x_axis] == max_study[x_axis]]
    for col in plot_columns:
        fig.add_trace(
            go.Scatter(
                x=df_plot2[y_axis], y=df_plot2[col],
                mode='lines+markers', name=col, showlegend=False,
                text=[f'Sample size: {row.sampleSize}<br>Cells per individuum: {row.totalCells}<br>Read depth: {row.readDepth}<br>{col}: {row[col]:.3f}' for _, row in df_plot2.iterrows()],
                hoverinfo='text'
            ),
            row=1, col=2
        )

    # Update layout
    fig.update_layout(
        xaxis_title=x_axis_label,
        xaxis2_title=y_axis_label,
        yaxis_title="Probability",
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    # Add vertical lines
    fig.add_vline(x=max_study[x_axis], line_dash="dot", row=1, col=1)
    fig.add_vline(x=max_study[y_axis], line_dash="dot", row=1, col=2)

    return fig

def json_safe(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.bool_)):
        return bool(obj)
    elif isinstance(obj, (np.string_, np.unicode_)):
        return str(obj)
    elif isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_safe(i) for i in obj]
    return obj

def extract_and_filter(celltypes, assay_filter=None, tissue_filter=None):
    assays = set()
    tissues = set()
    filtered_celltypes = celltypes

    if assay_filter and assay_filter != "All":
        filtered_celltypes = [ct for ct in filtered_celltypes if ct.startswith(assay_filter)]
    
    if tissue_filter and tissue_filter != "All":
        filtered_celltypes = [ct for ct in filtered_celltypes if ct.split('_')[1] == tissue_filter]

    for celltype in celltypes:
        parts = celltype.split('_')
        if len(parts) >= 3:
            assays.add(parts[0])
            tissues.add(parts[1])
    
    return sorted(list(assays)), sorted(list(tissues)), filtered_celltypes

# Callback functions to update session state
def update_assay():
    st.session_state.tissue = "All"


def perform_analysis():
    st.title("Detect DE/eQTL genes")
    scatter_file_id   = "1NkBP3AzLWuXKeYwgtVdTYxrzLjCuqLkR"
    influence_file_id = "1viAH5OEyhSoQjdGHi2Cm0_tFHrr1Z3GQ"

    if 'assay' not in st.session_state:
        st.session_state.assay = "All"
    if 'tissue' not in st.session_state:
        st.session_state.tissue = "All"

    # Custom CSS for the hover effect
    st.markdown("""
        <style>
        .hover-text {
            position: relative;
            display: inline-block;
            cursor: help;
        }

        .hover-text .hover-content {
            visibility: hidden;
            width: 510px;
            background-color: #1E2A3A;
            color: #fff;
            text-align: left;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1;
            top: 0;
            left: 0;
            opacity: 0;
            transition: opacity 0.3s;
            transform: translateX(-570px);
        }

        .hover-text:hover .hover-content {
            visibility: visible;
            opacity: 1;
        }
        </style>
                

        <script>
            var elements = document.getElementsByClassName('hover-text');
            for (var i = 0; i < elements.length; i++) {
                elements[i].addEventListener('touchstart', function() {
                    var content = this.getElementsByClassName('hover-content')[0];
                    content.style.visibility = content.style.visibility === 'visible' ? 'hidden' : 'visible';
                    content.style.opacity = content.style.opacity === '1' ? '0' : '1';
                });
            }
        </script>
        """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'scatter_data' not in st.session_state:
        st.session_state.scatter_data = None
    if 'influence_data' not in st.session_state:
        st.session_state.influence_data = None
    if 'success_message' not in st.session_state:
        st.session_state.success_message = st.empty()

    all_celltypes = [
        "10x 5' v1_blood_CD16-negative, CD56-bright natural killer cell, human","10x 5' v1_blood_naive B cell","10x 5' v1_blood_plasmacytoid dendritic cell","10x 5' v1_blood_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_blood_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v1_blood_CD14-low, CD16-positive monocyte","10x 5' v1_blood_CD14-positive monocyte","10x 5' v1_blood_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_blood_CD8-positive, alpha-beta memory T cell","10x 5' v1_blood_mature NK T cell","10x 5' v1_blood_memory B cell","10x 5' v1_blood_mucosal invariant T cell","10x 5' v1_blood_T cell","10x 5' v1_blood_natural killer cell","10x 5' v1_blood_regulatory T cell","10x 5' v1_blood_conventional dendritic cell","10x 5' v1_blood_platelet","10x 5' v1_blood_plasma cell","10x 5' v1_blood_B cell","10x 5' v1_blood_gamma-delta T cell","10x 5' v1_blood_plasmablast","10x 5' v1_blood_erythrocyte","10x 5' v1_blood_hematopoietic stem cell","10x 3' v2_gastrocnemius_slow muscle cell","10x 3' v2_gastrocnemius_skeletal muscle fiber","10x 3' v2_gastrocnemius_endothelial cell of vascular tree","10x 3' v2_gastrocnemius_skeletal muscle fibroblast","10x 3' v2_gastrocnemius_fast muscle cell","10x 3' v2_breast_luminal epithelial cell of mammary gland","10x 3' v2_breast_subcutaneous fat cell","10x 3' v2_breast_macrophage","10x 3' v2_breast_endothelial cell of vascular tree","10x 3' v2_mucosa_squamous epithelial cell","10x 3' v2_mucosa_basal cell","10x 3' v2_mucosa_myoepithelial cell of mammary gland","10x 3' v2_mucosa_endothelial cell of vascular tree","10x 3' v2_mucosa_basal epithelial cell of tracheobronchial tree","10x 3' v2_mucosa_glandular epithelial cell","10x 3' v2_mucosa_fibroblast","10x 3' v2_mucosa_endothelial cell of lymphatic vessel","10x 3' v2_mucosa_contractile cell","10x 3' v2_mucosa_macrophage","10x 3' v2_mucosa_T cell","10x 3' v2_esophagus muscularis mucosa_smooth muscle cell","10x 3' v2_esophagus muscularis mucosa_enteric smooth muscle cell","10x 3' v2_esophagus muscularis mucosa_endothelial cell of vascular tree","10x 3' v2_esophagus muscularis mucosa_endothelial cell of lymphatic vessel","10x 3' v2_esophagus muscularis mucosa_fibroblast","10x 3' v2_esophagus muscularis mucosa_macrophage","10x 3' v2_esophagus muscularis mucosa_mast cell","10x 3' v2_esophagus muscularis mucosa_fat cell","10x 3' v2_anterior wall of left ventricle_cardiac muscle cell","10x 3' v2_anterior wall of left ventricle_endothelial cell of vascular tree","10x 3' v2_anterior wall of left ventricle_fibroblast","10x 3' v2_anterior wall of left ventricle_contractile cell","10x 3' v2_anterior wall of left ventricle_macrophage","10x 3' v2_anterior wall of left ventricle_subcutaneous fat cell","10x 3' v2_anterior wall of left ventricle_professional antigen presenting cell","10x 3' v2_anterior wall of left ventricle_T cell","10x 3' v2_anterior wall of left ventricle_fibroblast of cardiac tissue","10x 3' v2_anterior wall of left ventricle_cardiac endothelial cell","10x 3' v2_lingula of left lung_epithelial cell of alveolus of lung","10x 3' v2_lingula of left lung_respiratory basal cell","10x 3' v2_lingula of left lung_alveolar macrophage","10x 3' v2_lingula of left lung_bronchial epithelial cell","10x 3' v2_lingula of left lung_macrophage","10x 3' v2_lingula of left lung_endothelial cell of vascular tree","10x 3' v2_lingula of left lung_fibroblast","10x 3' v2_lingula of left lung_endothelial cell of lymphatic vessel","10x 3' v2_prostate gland_luminal cell of prostate epithelium","10x 3' v2_prostate gland_epithelial cell of prostate","10x 3' v2_prostate gland_basal epithelial cell of prostatic duct","10x 3' v2_prostate gland_smooth muscle cell of prostate","10x 3' v2_prostate gland_skin fibroblast","10x 3' v2_prostate gland_endothelial cell of vascular tree","10x 3' v2_prostate gland_macrophage","10x 3' v2_prostate gland_endothelial cell of lymphatic vessel","10x 3' v2_skin of leg_epithelial cell of sweat gland","10x 3' v2_skin of leg_basal cell of epidermis","10x 3' v2_skin of leg_sebaceous gland cell","10x 3' v2_skin of leg_keratinocyte","10x 3' v2_skin of leg_skin fibroblast","10x 5' v1_ileum_CD4-positive helper T cell","10x 5' v1_ileum_CD8-positive, alpha-beta memory T cell","10x 5' v1_ileum_gamma-delta T cell","10x 5' v1_ileum_memory B cell","10x 5' v1_lung_conventional dendritic cell","10x 5' v1_lung_macrophage","10x 5' v1_lung_alveolar macrophage","10x 5' v1_lung_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_lung_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_lung_CD4-positive helper T cell","10x 5' v1_lung_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_lung_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_lung_classical monocyte","10x 5' v1_lung_mast cell","10x 5' v1_lung_non-classical monocyte","10x 5' v1_lung_animal cell","10x 5' v1_thoracic lymph node_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_thoracic lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v1_thoracic lymph node_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_thoracic lymph node_naive B cell","10x 5' v1_thoracic lymph node_classical monocyte","10x 5' v1_thoracic lymph node_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_thoracic lymph node_memory B cell","10x 5' v1_thoracic lymph node_regulatory T cell","10x 5' v1_thoracic lymph node_CD16-negative, CD56-bright natural killer cell, human","10x 5' v1_thoracic lymph node_T follicular helper cell","10x 5' v1_thoracic lymph node_plasma cell","10x 5' v1_thoracic lymph node_alpha-beta T cell","10x 5' v1_thoracic lymph node_conventional dendritic cell","10x 5' v1_thoracic lymph node_macrophage","10x 5' v1_thoracic lymph node_CD4-positive helper T cell","10x 5' v1_thoracic lymph node_germinal center B cell","10x 5' v1_thoracic lymph node_mucosal invariant T cell","10x 5' v1_thoracic lymph node_alveolar macrophage","10x 5' v1_thoracic lymph node_dendritic cell, human","10x 5' v1_thoracic lymph node_group 3 innate lymphoid cell","10x 5' v1_thoracic lymph node_CD8-positive, alpha-beta memory T cell","10x 5' v1_thoracic lymph node_lymphocyte","10x 5' v1_thoracic lymph node_animal cell","10x 5' v1_mesenteric lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v1_mesenteric lymph node_naive B cell","10x 5' v1_mesenteric lymph node_memory B cell","10x 5' v1_mesenteric lymph node_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_mesenteric lymph node_T follicular helper cell","10x 5' v1_mesenteric lymph node_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_mesenteric lymph node_regulatory T cell","10x 5' v1_mesenteric lymph node_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_mesenteric lymph node_lymphocyte","10x 5' v1_mesenteric lymph node_germinal center B cell","10x 5' v1_mesenteric lymph node_CD8-positive, alpha-beta memory T cell","10x 5' v1_mesenteric lymph node_group 3 innate lymphoid cell","10x 5' v1_bone marrow_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_bone marrow_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_bone marrow_classical monocyte","10x 5' v1_bone marrow_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_bone marrow_erythroid lineage cell","10x 5' v1_bone marrow_animal cell","10x 5' v1_bone marrow_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_bone marrow_mucosal invariant T cell","10x 5' v1_bone marrow_progenitor cell","10x 5' v1_bone marrow_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v1_bone marrow_gamma-delta T cell","10x 5' v1_bone marrow_naive B cell","10x 5' v1_bone marrow_megakaryocyte","10x 5' v1_bone marrow_memory B cell","10x 5' v1_bone marrow_conventional dendritic cell","10x 5' v1_bone marrow_CD16-negative, CD56-bright natural killer cell, human","10x 5' v1_bone marrow_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_bone marrow_non-classical monocyte","10x 5' v1_bone marrow_lymphocyte","10x 5' v1_bone marrow_plasmacytoid dendritic cell","10x 5' v1_bone marrow_regulatory T cell","10x 5' v1_skeletal muscle tissue_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_skeletal muscle tissue_classical monocyte","10x 5' v1_skeletal muscle tissue_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_liver_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_liver_mucosal invariant T cell","10x 5' v1_liver_macrophage","10x 5' v1_liver_classical monocyte","10x 5' v1_liver_CD16-negative, CD56-bright natural killer cell, human","10x 5' v1_liver_naive B cell","10x 5' v1_liver_gamma-delta T cell","10x 5' v1_liver_animal cell","10x 5' v1_liver_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_liver_conventional dendritic cell","10x 5' v1_liver_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_liver_non-classical monocyte","10x 5' v1_liver_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_liver_plasma cell","10x 5' v1_liver_memory B cell","10x 5' v1_spleen_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_spleen_memory B cell","10x 5' v1_spleen_naive B cell","10x 5' v1_spleen_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_spleen_regulatory T cell","10x 5' v1_spleen_animal cell","10x 5' v1_spleen_gamma-delta T cell","10x 5' v1_spleen_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v1_spleen_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_spleen_mucosal invariant T cell","10x 5' v1_spleen_macrophage","10x 5' v1_spleen_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_spleen_classical monocyte","10x 5' v1_spleen_T follicular helper cell","10x 5' v1_spleen_CD16-negative, CD56-bright natural killer cell, human","10x 5' v1_spleen_conventional dendritic cell","10x 5' v1_spleen_non-classical monocyte","10x 5' v1_spleen_CD16-positive, CD56-dim natural killer cell, human","10x 5' v1_spleen_CD8-positive, alpha-beta memory T cell","10x 5' v1_spleen_plasma cell","10x 5' v1_spleen_CD4-positive helper T cell","10x 5' v1_spleen_lymphocyte","10x 5' v1_spleen_plasmablast","10x 5' v1_spleen_germinal center B cell","10x 5' v1_omentum_memory B cell","10x 5' v1_omentum_CD4-positive helper T cell","10x 5' v1_omentum_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_liver_lymphocyte","10x 5' v1_liver_CD8-positive, alpha-beta memory T cell","10x 5' v1_liver_CD4-positive helper T cell","10x 5' v1_caecum_gamma-delta T cell","10x 5' v1_caecum_CD8-positive, alpha-beta memory T cell","10x 5' v1_caecum_plasma cell","10x 5' v1_bone marrow_plasma cell","10x 5' v1_thymus_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v1_thymus_memory B cell","10x 5' v1_duodenum_CD4-positive helper T cell","10x 5' v1_duodenum_CD8-positive, alpha-beta memory T cell","10x 5' v1_duodenum_alpha-beta T cell","10x 5' v1_blood_classical monocyte","10x 5' v1_blood_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_blood_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v1_blood_non-classical monocyte","10x 5' v1_blood_megakaryocyte","10x 5' v1_blood_lymphocyte","10x 5' v1_blood_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v1_skeletal muscle tissue_memory B cell","10x 5' v1_skeletal muscle tissue_effector memory CD4-positive, alpha-beta T cell","10x 5' v1_skeletal muscle tissue_non-classical monocyte","10x 5' v1_transverse colon_plasma cell","10x 5' v2_spleen_naive B cell","10x 5' v2_spleen_T follicular helper cell","10x 5' v2_spleen_mucosal invariant T cell","10x 5' v2_spleen_memory B cell","10x 5' v2_spleen_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_spleen_regulatory T cell","10x 5' v2_spleen_classical monocyte","10x 5' v2_spleen_CD16-positive, CD56-dim natural killer cell, human","10x 5' v2_spleen_conventional dendritic cell","10x 5' v2_spleen_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v2_spleen_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_spleen_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_spleen_germinal center B cell","10x 5' v2_mesenteric lymph node_memory B cell","10x 5' v2_spleen_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_spleen_animal cell","10x 5' v2_spleen_gamma-delta T cell","10x 5' v2_spleen_macrophage","10x 5' v2_spleen_lymphocyte","10x 5' v2_spleen_CD8-positive, alpha-beta memory T cell","10x 5' v2_spleen_alpha-beta T cell","10x 5' v2_spleen_CD4-positive helper T cell","10x 5' v2_spleen_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v2_mesenteric lymph node_regulatory T cell","10x 5' v2_mesenteric lymph node_naive B cell","10x 5' v2_mesenteric lymph node_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v2_spleen_non-classical monocyte","10x 5' v2_spleen_plasma cell","10x 5' v2_mesenteric lymph node_animal cell","10x 5' v2_spleen_group 3 innate lymphoid cell","10x 5' v2_mesenteric lymph node_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_mesenteric lymph node_T follicular helper cell","10x 5' v2_mesenteric lymph node_group 3 innate lymphoid cell","10x 5' v2_mesenteric lymph node_lymphocyte","10x 5' v2_mesenteric lymph node_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v2_mesenteric lymph node_CD8-positive, alpha-beta memory T cell","10x 5' v2_lamina propria_CD4-positive helper T cell","10x 5' v2_thoracic lymph node_regulatory T cell","10x 5' v2_thoracic lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_thoracic lymph node_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_thoracic lymph node_lymphocyte","10x 5' v2_thoracic lymph node_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_thoracic lymph node_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v2_lamina propria_CD8-positive, alpha-beta memory T cell","10x 5' v2_thoracic lymph node_memory B cell","10x 5' v2_lamina propria_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_thoracic lymph node_T follicular helper cell","10x 5' v2_thoracic lymph node_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_thoracic lymph node_naive B cell","10x 5' v2_thoracic lymph node_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v2_jejunal epithelium_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_jejunal epithelium_naive B cell","10x 5' v2_lamina propria_plasma cell","10x 5' v2_thoracic lymph node_plasma cell","10x 5' v2_jejunal epithelium_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_jejunal epithelium_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_thoracic lymph node_CD4-positive helper T cell","10x 5' v2_jejunal epithelium_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_jejunal epithelium_CD4-positive helper T cell","10x 5' v2_lamina propria_macrophage","10x 5' v2_lamina propria_gamma-delta T cell","10x 5' v2_jejunal epithelium_gamma-delta T cell","10x 5' v2_mesenteric lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_mesenteric lymph node_CD16-positive, CD56-dim natural killer cell, human","10x 5' v2_mesenteric lymph node_CD4-positive helper T cell","10x 5' v2_mesenteric lymph node_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_mesenteric lymph node_gamma-delta T cell","10x 5' v2_mesenteric lymph node_mucosal invariant T cell","10x 5' v2_bone marrow_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v2_bone marrow_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_bone marrow_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_bone marrow_CD4-positive helper T cell","10x 5' v2_bone marrow_naive thymus-derived CD8-positive, alpha-beta T cell","10x 5' v2_bone marrow_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_bone marrow_regulatory T cell","10x 5' v2_bone marrow_erythroid lineage cell","10x 5' v2_blood_CD16-positive, CD56-dim natural killer cell, human","10x 5' v2_bone marrow_naive B cell","10x 5' v2_blood_naive thymus-derived CD4-positive, alpha-beta T cell","10x 5' v2_bone marrow_gamma-delta T cell","10x 5' v2_bone marrow_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_bone marrow_mucosal invariant T cell","10x 5' v2_bone marrow_memory B cell","10x 5' v2_blood_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_blood_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_bone marrow_CD16-positive, CD56-dim natural killer cell, human","10x 5' v2_bone marrow_animal cell","10x 5' v2_bone marrow_classical monocyte","10x 5' v2_bone marrow_progenitor cell","10x 5' v2_bone marrow_non-classical monocyte","10x 5' v2_mesenteric lymph node_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_liver_CD16-negative, CD56-bright natural killer cell, human","10x 5' v2_liver_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 5' v2_liver_gamma-delta T cell","10x 5' v2_liver_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 5' v2_liver_CD16-positive, CD56-dim natural killer cell, human","10x 5' v2_liver_mucosal invariant T cell","10x 5' v2_liver_CD4-positive helper T cell","10x 5' v2_liver_classical monocyte","10x 5' v2_liver_non-classical monocyte","10x 5' v2_liver_effector memory CD4-positive, alpha-beta T cell","10x 5' v2_lung_alveolar macrophage","10x 5' v2_jejunal epithelium_CD8-positive, alpha-beta memory T cell","10x 5' v2_jejunal epithelium_alpha-beta T cell","10x 3' v3_lamina propria_CD8-positive, alpha-beta memory T cell","10x 3' v3_lung_CD4-positive helper T cell","10x 3' v3_bone marrow_CD16-negative, CD56-bright natural killer cell, human","10x 3' v3_jejunal epithelium_CD8-positive, alpha-beta memory T cell","10x 3' v3_blood_classical monocyte","10x 3' v3_spleen_CD16-negative, CD56-bright natural killer cell, human","10x 3' v3_spleen_mucosal invariant T cell","10x 3' v3_blood_alpha-beta T cell","10x 3' v3_blood_CD16-positive, CD56-dim natural killer cell, human","10x 3' v3_blood_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_thoracic lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_bone marrow_classical monocyte","10x 3' v3_spleen_CD16-positive, CD56-dim natural killer cell, human","10x 3' v3_spleen_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 3' v3_jejunal epithelium_gamma-delta T cell","10x 3' v3_bone marrow_animal cell","10x 3' v3_lung_CD16-negative, CD56-bright natural killer cell, human","10x 3' v3_thoracic lymph node_regulatory T cell","10x 3' v3_spleen_memory B cell","10x 3' v3_spleen_plasmablast","10x 3' v3_lamina propria_CD4-positive helper T cell","10x 3' v3_lung_effector memory CD4-positive, alpha-beta T cell","10x 3' v3_jejunal epithelium_CD4-positive helper T cell","10x 3' v3_thoracic lymph node_memory B cell","10x 3' v3_spleen_effector memory CD4-positive, alpha-beta T cell","10x 3' v3_bone marrow_naive thymus-derived CD8-positive, alpha-beta T cell","10x 3' v3_lung_classical monocyte","10x 3' v3_lamina propria_gamma-delta T cell","10x 3' v3_bone marrow_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_bone marrow_naive B cell","10x 3' v3_lung_mast cell","10x 3' v3_spleen_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_blood_naive thymus-derived CD8-positive, alpha-beta T cell","10x 3' v3_thoracic lymph node_T follicular helper cell","10x 3' v3_thoracic lymph node_effector memory CD4-positive, alpha-beta T cell","10x 3' v3_blood_effector memory CD4-positive, alpha-beta T cell","10x 3' v3_blood_CD16-negative, CD56-bright natural killer cell, human","10x 3' v3_spleen_naive B cell","10x 3' v3_spleen_naive thymus-derived CD8-positive, alpha-beta T cell","10x 3' v3_spleen_classical monocyte","10x 3' v3_lamina propria_mast cell","10x 3' v3_bone marrow_CD16-positive, CD56-dim natural killer cell, human","10x 3' v3_spleen_gamma-delta T cell","10x 3' v3_lung_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 3' v3_bone marrow_progenitor cell","10x 3' v3_blood_lymphocyte","10x 3' v3_bone marrow_lymphocyte","10x 3' v3_bone marrow_regulatory T cell","10x 3' v3_bone marrow_memory B cell","10x 3' v3_lung_CD16-positive, CD56-dim natural killer cell, human","10x 3' v3_spleen_lymphocyte","10x 3' v3_bone marrow_effector memory CD4-positive, alpha-beta T cell","10x 3' v3_bone marrow_non-classical monocyte","10x 3' v3_spleen_T follicular helper cell","10x 3' v3_spleen_regulatory T cell","10x 3' v3_spleen_group 3 innate lymphoid cell","10x 3' v3_lung_alveolar macrophage","10x 3' v3_bone marrow_erythroid lineage cell","10x 3' v3_lung_regulatory T cell","10x 3' v3_bone marrow_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 3' v3_spleen_plasma cell","10x 3' v3_spleen_CD4-positive helper T cell","10x 3' v3_thoracic lymph node_lymphocyte","10x 3' v3_thoracic lymph node_CD16-negative, CD56-bright natural killer cell, human","10x 3' v3_bone marrow_CD4-positive helper T cell","10x 3' v3_thoracic lymph node_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 3' v3_thoracic lymph node_CD4-positive helper T cell","10x 3' v3_bone marrow_conventional dendritic cell","10x 3' v3_lamina propria_macrophage","10x 3' v3_lung_conventional dendritic cell","10x 3' v3_lamina propria_conventional dendritic cell","10x 3' v3_bone marrow_plasmacytoid dendritic cell","10x 3' v3_lung_naive B cell","10x 3' v3_blood_regulatory T cell","10x 3' v3_lamina propria_plasma cell","10x 3' v3_blood_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 3' v3_bone marrow_plasmablast","10x 3' v3_blood_T follicular helper cell","10x 3' v3_lung_non-classical monocyte","10x 3' v3_thoracic lymph node_alpha-beta T cell","10x 3' v3_spleen_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 3' v3_thoracic lymph node_plasma cell","10x 3' v3_blood_animal cell","10x 3' v3_blood_progenitor cell","10x 3' v3_bone marrow_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 3' v3_lung_lymphocyte","10x 3' v3_lung_macrophage","10x 3' v3_spleen_progenitor cell","10x 3' v3_blood_naive B cell","10x 3' v3_lung_animal cell","10x 3' v3_lung_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_spleen_CD8-positive, alpha-beta memory T cell","10x 3' v3_thoracic lymph node_naive B cell","10x 3' v3_thoracic lymph node_group 3 innate lymphoid cell","10x 3' v3_spleen_mast cell","10x 3' v3_lung_dendritic cell, human","10x 3' v3_bone marrow_T follicular helper cell","10x 3' v3_spleen_plasmacytoid dendritic cell","10x 3' v3_lung_mucosal invariant T cell","10x 3' v3_thoracic lymph node_mucosal invariant T cell","10x 3' v3_lung_gamma-delta T cell","10x 3' v3_bone marrow_mast cell","10x 3' v3_thoracic lymph node_plasmablast","10x 3' v3_lung_effector memory CD8-positive, alpha-beta T cell, terminally differentiated","10x 3' v3_bone marrow_gamma-delta T cell","10x 3' v3_spleen_animal cell","10x 3' v3_bone marrow_plasma cell","10x 3' v3_blood_CD8-positive, alpha-beta memory T cell, CD45RO-positive","10x 3' v3_blood_conventional dendritic cell","10x 3' v3_thoracic lymph node_mast cell","10x 3' v3_bone marrow_mucosal invariant T cell","10x 3' v3_thoracic lymph node_naive thymus-derived CD8-positive, alpha-beta T cell","10x 3' v3_thoracic lymph node_gamma-delta T cell","10x 3' v3_blood_memory B cell","10x 3' v3_thoracic lymph node_animal cell","10x 3' v3_lung_T follicular helper cell","10x 3' v3_lamina propria_animal cell","10x 3' v3_jejunal epithelium_mast cell","10x 3' v3_lamina propria_lymphocyte","10x 3' v2_limb muscle_macrophage","10x 3' v2_limb muscle_endothelial cell","10x 3' v2_limb muscle_mesenchymal stem cell","10x 3' v2_limb muscle_smooth muscle cell","10x 3' v2_limb muscle_Schwann cell","10x 3' v2_limb muscle_skeletal muscle satellite cell","10x 3' v2_limb muscle_B cell","10x 3' v2_limb muscle_cell of skeletal muscle","10x 3' v2_limb muscle_T cell","10x 3' v3_liver_macrophage","10x 3' v3_liver_monocyte","10x 3' v3_liver_endothelial cell of hepatic sinusoid","10x 3' v3_liver_mature NK T cell","10x 3' v3_liver_hepatocyte","10x 3' v3_trachea_macrophage","10x 3' v3_trachea_tracheal goblet cell","10x 3' v3_trachea_fibroblast","10x 3' v3_trachea_endothelial cell","10x 3' v3_trachea_smooth muscle cell","10x 3' v3_trachea_ciliated cell","10x 3' v3_trachea_secretory cell","10x 3' v3_trachea_T cell","10x 3' v3_trachea_mast cell","10x 3' v3_trachea_plasma cell","10x 3' v3_trachea_CD8-positive, alpha-beta T cell","10x 3' v3_trachea_B cell","10x 3' v3_trachea_neutrophil","10x 3' v3_blood_erythrocyte","10x 3' v3_blood_CD4-positive, alpha-beta memory T cell","10x 3' v3_blood_CD8-positive, alpha-beta cytokine secreting effector T cell","10x 3' v3_blood_neutrophil","10x 3' v3_blood_mature NK T cell","10x 3' v3_blood_type I NK T cell","10x 3' v3_blood_CD8-positive, alpha-beta T cell","10x 3' v3_blood_plasma cell","10x 3' v3_blood_hematopoietic stem cell","10x 3' v3_inguinal lymph node_B cell","10x 3' v3_inguinal lymph node_effector CD8-positive, alpha-beta T cell","10x 3' v3_inguinal lymph node_T cell","10x 3' v3_inguinal lymph node_type I NK T cell","10x 3' v3_inguinal lymph node_effector CD4-positive, alpha-beta T cell","10x 3' v3_inguinal lymph node_innate lymphoid cell","10x 3' v3_inguinal lymph node_plasma cell","10x 3' v3_lymph node_effector CD4-positive, alpha-beta T cell","10x 3' v3_lymph node_type I NK T cell","10x 3' v3_lymph node_effector CD8-positive, alpha-beta T cell","10x 3' v3_lymph node_innate lymphoid cell","10x 3' v3_lymph node_macrophage","10x 3' v3_lymph node_regulatory T cell","10x 3' v3_lymph node_T cell","10x 3' v3_lymph node_plasma cell","10x 3' v3_lymph node_mature NK T cell","10x 3' v3_lymph node_mast cell","10x 3' v3_lymph node_CD141-positive myeloid dendritic cell","10x 3' v3_lymph node_intermediate monocyte","10x 3' v3_lymph node_stromal cell","10x 3' v3_lymph node_CD1c-positive myeloid dendritic cell","10x 3' v3_lymph node_classical monocyte","10x 3' v3_lymph node_endothelial cell","10x 3' v3_parotid gland_naive B cell","10x 3' v3_parotid gland_memory B cell","10x 3' v3_parotid gland_CD4-positive helper T cell","10x 3' v3_parotid gland_mature NK T cell","10x 3' v3_parotid gland_fibroblast","10x 3' v3_parotid gland_endothelial cell of lymphatic vessel","10x 3' v3_parotid gland_adventitial cell","10x 3' v3_parotid gland_B cell","10x 3' v3_parotid gland_endothelial cell","10x 3' v3_parotid gland_monocyte","10x 3' v3_parotid gland_duct epithelial cell","10x 3' v3_parotid gland_CD8-positive, alpha-beta T cell","10x 3' v3_parotid gland_neutrophil","10x 3' v3_spleen_macrophage","10x 3' v3_spleen_intermediate monocyte","10x 3' v3_spleen_endothelial cell","10x 3' v3_spleen_neutrophil","10x 3' v3_spleen_CD4-positive, alpha-beta memory T cell","10x 3' v3_spleen_type I NK T cell","10x 3' v3_spleen_mature NK T cell","10x 3' v3_spleen_innate lymphoid cell","10x 3' v3_spleen_erythrocyte","10x 3' v3_spleen_hematopoietic stem cell","10x 3' v3_anterior part of tongue_epithelial cell","10x 3' v3_posterior part of tongue_leukocyte","10x 3' v3_posterior part of tongue_fibroblast","10x 3' v3_posterior part of tongue_vein endothelial cell","10x 3' v3_posterior part of tongue_pericyte","10x 3' v3_posterior part of tongue_keratinocyte","10x 3' v3_mammary gland_fibroblast of breast","10x 3' v3_mammary gland_T cell","10x 3' v3_mammary gland_macrophage","10x 3' v3_mammary gland_pericyte","10x 3' v3_mammary gland_vascular associated smooth muscle cell","10x 3' v3_mammary gland_vein endothelial cell","10x 3' v3_mammary gland_basal cell","10x 3' v3_mammary gland_plasma cell","10x 3' v3_mammary gland_endothelial cell of artery","10x 3' v3_endometrium_T cell","10x 3' v3_endometrium_macrophage","10x 3' v3_endometrium_epithelial cell of uterus","10x 3' v3_endometrium_endothelial cell","10x 3' v3_endometrium_epithelial cell","10x 3' v3_endometrium_endothelial cell of lymphatic vessel","10x 3' v3_myometrium_vascular associated smooth muscle cell","10x 3' v3_myometrium_myometrial cell","10x 3' v3_myometrium_endothelial cell","10x 3' v3_myometrium_fibroblast","10x 3' v3_myometrium_pericyte","10x 3' v3_eye_conjunctival epithelial cell","10x 3' v3_eye_microglial cell","10x 3' v3_eye_eye photoreceptor cell","10x 3' v3_eye_Mueller cell","10x 3' v3_eye_T cell","10x 3' v3_eye_epithelial cell of lacrimal sac","10x 3' v3_eye_keratocyte","10x 3' v3_conjunctiva_conjunctival epithelial cell","10x 3' v3_adipose tissue_endothelial cell","10x 3' v3_adipose tissue_T cell","10x 3' v3_adipose tissue_macrophage","10x 3' v3_adipose tissue_myofibroblast cell","10x 3' v3_adipose tissue_mesenchymal stem cell","10x 3' v3_adipose tissue_neutrophil","10x 3' v3_subcutaneous adipose tissue_mature NK T cell","10x 3' v3_subcutaneous adipose tissue_myofibroblast cell","10x 3' v3_subcutaneous adipose tissue_macrophage","10x 3' v3_subcutaneous adipose tissue_endothelial cell","10x 3' v3_subcutaneous adipose tissue_T cell","10x 3' v3_skin of body_macrophage","10x 3' v3_skin of body_stromal cell","10x 3' v3_skin of body_CD8-positive, alpha-beta memory T cell","10x 3' v3_skin of body_mature NK T cell","10x 3' v3_skin of body_mast cell","10x 3' v3_skin of body_muscle cell","10x 3' v3_skin of body_CD8-positive, alpha-beta cytotoxic T cell","10x 3' v3_skin of body_CD1c-positive myeloid dendritic cell","10x 3' v3_skin of body_endothelial cell","10x 3' v3_skin of body_CD4-positive, alpha-beta memory T cell","10x 3' v3_skin of body_naive thymus-derived CD8-positive, alpha-beta T cell","10x 3' v3_skin of body_epithelial cell","10x 3' v3_bone marrow_monocyte","10x 3' v3_bone marrow_hematopoietic stem cell","10x 3' v3_bone marrow_erythroid progenitor cell","10x 3' v3_bone marrow_mature NK T cell","10x 3' v3_bone marrow_granulocyte","10x 3' v3_bone marrow_macrophage","10x 3' v3_bone marrow_common myeloid progenitor","10x 3' v3_bone marrow_CD8-positive, alpha-beta T cell","10x 3' v3_bone marrow_CD4-positive, alpha-beta T cell","10x 3' v3_bone marrow_neutrophil","10x 3' v3_cardiac atrium_cardiac endothelial cell","10x 3' v3_cardiac atrium_hepatocyte","10x 3' v3_cardiac ventricle_cardiac muscle cell","10x 3' v3_cardiac ventricle_cardiac endothelial cell","10x 3' v3_cardiac ventricle_hepatocyte","10x 3' v3_cardiac ventricle_fibroblast of cardiac tissue","10x 3' v3_exocrine pancreas_pancreatic acinar cell","10x 3' v3_exocrine pancreas_T cell","10x 3' v3_exocrine pancreas_endothelial cell","10x 3' v3_exocrine pancreas_myeloid cell","10x 3' v3_exocrine pancreas_pancreatic stellate cell","10x 3' v3_exocrine pancreas_pancreatic ductal cell","10x 3' v3_exocrine pancreas_plasma cell","10x 3' v3_exocrine pancreas_type B pancreatic cell","10x 3' v3_prostate gland_epithelial cell","10x 3' v3_prostate gland_fibroblast","10x 3' v3_prostate gland_club cell","10x 3' v3_prostate gland_macrophage","10x 3' v3_prostate gland_mature NK T cell","10x 3' v3_prostate gland_CD8-positive, alpha-beta T cell","10x 3' v3_prostate gland_luminal cell of prostate epithelium","10x 3' v3_prostate gland_endothelial cell","10x 3' v3_prostate gland_smooth muscle cell","Smart-seq2_subcutaneous adipose tissue_fibroblast","Smart-seq2_skin of abdomen_endothelial cell","Smart-seq2_skin of abdomen_mast cell","Smart-seq2_skin of chest_endothelial cell","Smart-seq2_bone marrow_CD4-positive, alpha-beta T cell","Smart-seq2_bone marrow_plasma cell","Smart-seq2_bone marrow_erythroid progenitor cell","Smart-seq2_uterus_epithelial cell of uterus","Smart-seq2_mammary gland_luminal epithelial cell of mammary gland","Smart-seq2_muscle of pelvic diaphragm_endothelial cell of vascular tree","Smart-seq2_trachea_ciliated cell","Smart-seq2_trachea_basal cell","Smart-seq2_trachea_fibroblast","Smart-seq2_spleen_memory B cell","Smart-seq2_spleen_plasma cell","Smart-seq2_spleen_mature NK T cell","Smart-seq2_lymph node_plasma cell","Smart-seq2_parotid gland_adventitial cell","Smart-seq2_posterior part of tongue_basal cell","Smart-seq2_prostate gland_epithelial cell","10x 3' v3_bone marrow_erythrocyte","10x 3' v3_liver_endothelial cell","10x 3' v3_liver_erythrocyte","10x 3' v3_parotid gland_macrophage","10x 3' v3_submandibular gland_basal cell","10x 3' v3_submandibular gland_plasma cell","10x 3' v3_submandibular gland_macrophage","10x 3' v3_submandibular gland_ionocyte","10x 3' v3_submandibular gland_duct epithelial cell","10x 3' v3_submandibular gland_endothelial cell of lymphatic vessel","10x 3' v3_submandibular gland_endothelial cell","10x 3' v3_submandibular gland_fibroblast","10x 3' v3_thymus_naive regulatory T cell","10x 3' v3_thymus_T follicular helper cell","10x 3' v3_thymus_CD8-positive, alpha-beta cytotoxic T cell","10x 3' v3_thymus_B cell","10x 3' v3_thymus_medullary thymic epithelial cell","10x 3' v3_thymus_macrophage","10x 3' v3_thymus_vascular associated smooth muscle cell","10x 3' v3_thymus_plasma cell","10x 3' v3_thymus_vein endothelial cell","10x 3' v3_thymus_capillary endothelial cell","10x 3' v3_thymus_endothelial cell of artery","10x 3' v3_thymus_mature NK T cell","10x 3' v3_thymus_monocyte","10x 3' v3_thymus_endothelial cell of lymphatic vessel","10x 3' v3_cornea_corneal epithelial cell","10x 3' v3_cornea_conjunctival epithelial cell","10x 3' v3_cornea_radial glial cell","10x 3' v3_cornea_stem cell","10x 3' v3_cornea_keratocyte","10x 3' v3_cornea_fibroblast","10x 3' v3_cornea_retinal blood vessel endothelial cell","10x 3' v3_cornea_melanocyte","10x 3' v3_retinal neural layer_eye photoreceptor cell","10x 3' v3_retinal neural layer_Mueller cell","10x 3' v3_sclera_retinal blood vessel endothelial cell","10x 3' v3_sclera_keratocyte","10x 3' v3_sclera_stromal cell","10x 3' v3_sclera_endothelial cell","10x 3' v3_sclera_macrophage","10x 3' v3_sclera_conjunctival epithelial cell","10x 3' v3_bladder organ_T cell","10x 3' v3_bladder organ_macrophage","10x 3' v3_bladder organ_myofibroblast cell","10x 3' v3_bladder organ_capillary endothelial cell","10x 3' v3_bladder organ_smooth muscle cell","10x 3' v3_bladder organ_pericyte","10x 3' v3_bladder organ_mast cell","10x 3' v3_bladder organ_mature NK T cell","10x 3' v3_bladder organ_endothelial cell of lymphatic vessel","10x 3' v3_bladder organ_vein endothelial cell","10x 3' v3_bladder organ_B cell","10x 3' v3_large intestine_CD4-positive, alpha-beta T cell","10x 3' v3_large intestine_enterocyte of epithelium of large intestine","10x 3' v3_large intestine_monocyte","10x 3' v3_large intestine_plasma cell","10x 3' v3_large intestine_CD8-positive, alpha-beta T cell","10x 3' v3_large intestine_fibroblast","10x 3' v3_large intestine_large intestine goblet cell","10x 3' v3_large intestine_paneth cell of colon","10x 3' v3_large intestine_B cell","10x 3' v3_large intestine_transit amplifying cell of colon","10x 3' v3_large intestine_intestinal enteroendocrine cell","10x 3' v3_lung_respiratory goblet cell","10x 3' v3_prostate gland_T cell","10x 3' v3_prostate gland_myeloid cell","10x 3' v3_small intestine_CD4-positive, alpha-beta T cell","10x 3' v3_small intestine_enterocyte of epithelium of small intestine","10x 3' v3_small intestine_neutrophil","10x 3' v3_small intestine_transit amplifying cell of small intestine","10x 3' v3_small intestine_small intestine goblet cell","10x 3' v3_small intestine_CD8-positive, alpha-beta T cell","10x 3' v3_small intestine_B cell","10x 3' v3_small intestine_monocyte","10x 3' v3_small intestine_paneth cell of epithelium of small intestine","10x 3' v3_small intestine_plasma cell","10x 3' v3_small intestine_mast cell","10x 3' v3_small intestine_intestinal enteroendocrine cell","10x 3' v3_small intestine_intestinal crypt stem cell of small intestine","10x 3' v3_skin of abdomen_mature NK T cell","10x 3' v3_skin of abdomen_stromal cell","10x 3' v3_skin of abdomen_endothelial cell","10x 3' v3_skin of abdomen_CD8-positive, alpha-beta memory T cell","10x 3' v3_skin of abdomen_mast cell","10x 3' v3_skin of abdomen_macrophage","10x 3' v3_skin of abdomen_muscle cell","10x 3' v3_skin of abdomen_T cell","10x 3' v3_skin of chest_endothelial cell","10x 3' v3_skin of chest_stromal cell","10x 3' v3_skin of chest_CD8-positive, alpha-beta memory T cell","10x 3' v3_skin of chest_muscle cell","10x 3' v3_skin of chest_mature NK T cell","10x 3' v3_thymus_DN3 thymocyte","10x 3' v3_thymus_DN1 thymic pro-T cell","10x 3' v3_thymus_innate lymphoid cell","10x 3' v3_anterior part of tongue_basal cell","10x 3' v3_anterior part of tongue_keratinocyte","10x 3' v3_anterior part of tongue_leukocyte","10x 3' v3_muscle of abdomen_mesenchymal stem cell","10x 3' v3_muscle of abdomen_skeletal muscle satellite stem cell","10x 3' v3_muscle of abdomen_capillary endothelial cell","10x 3' v3_muscle of abdomen_pericyte","10x 3' v3_muscle of abdomen_macrophage","10x 3' v3_muscle of abdomen_endothelial cell of vascular tree","10x 3' v3_muscle of pelvic diaphragm_mesenchymal stem cell","10x 3' v3_muscle of pelvic diaphragm_macrophage","10x 3' v3_muscle of pelvic diaphragm_skeletal muscle satellite stem cell","10x 3' v3_muscle of pelvic diaphragm_endothelial cell of vascular tree","10x 3' v3_muscle of pelvic diaphragm_T cell","10x 3' v3_vasculature_smooth muscle cell","10x 3' v3_vasculature_macrophage","10x 3' v3_vasculature_pericyte","10x 3' v3_coronary artery_smooth muscle cell","10x 3' v3_coronary artery_T cell","10x 3' v3_coronary artery_macrophage","10x 3' v3_coronary artery_endothelial cell of artery","10x 3' v3_coronary artery_pericyte","10x 3' v3_bladder organ_plasma cell","Smart-seq2_bladder organ_bladder urothelial cell","10x 3' v3_blood_CD4-positive, alpha-beta T cell","10x 3' v3_blood_monocyte","10x 3' v3_blood_macrophage","10x 3' v3_kidney_kidney epithelial cell","10x 3' v3_kidney_B cell","10x 3' v3_kidney_CD8-positive, alpha-beta T cell","10x 3' v3_kidney_macrophage","10x 3' v3_kidney_CD4-positive helper T cell","Smart-seq2_kidney_kidney epithelial cell","10x 3' v3_large intestine_enterocyte","10x 3' v3_large intestine_intestinal crypt stem cell","10x 3' v3_large intestine_goblet cell","10x 3' v3_lung_basophil","10x 3' v3_lung_lung ciliated cell","10x 3' v3_lung_dendritic cell","10x 3' v3_lung_CD4-positive, alpha-beta T cell","10x 3' v3_lung_basal cell","10x 3' v3_lung_plasma cell","10x 3' v3_lung_CD8-positive, alpha-beta T cell","10x 3' v3_lung_capillary endothelial cell","10x 3' v3_lung_type I pneumocyte","10x 3' v3_lung_vein endothelial cell","10x 3' v3_lung_fibroblast","10x 3' v3_lung_club cell","10x 3' v3_lung_lung microvascular endothelial cell","Smart-seq2_lung_type II pneumocyte","Smart-seq2_lung_macrophage","Smart-seq2_lung_basal cell","Smart-seq2_lung_adventitial cell","10x 3' v3_lung_intermediate monocyte","10x 3' v3_lymph node_naive B cell","10x 3' v3_lymph node_memory B cell","10x 3' v3_lymph node_naive thymus-derived CD4-positive, alpha-beta T cell","10x 3' v3_lymph node_CD4-positive, alpha-beta memory T cell","10x 3' v3_lymph node_CD8-positive, alpha-beta memory T cell","Smart-seq2_lymph node_memory B cell","Smart-seq2_inguinal lymph node_memory B cell","10x 3' v3_muscle tissue_skeletal muscle satellite stem cell","10x 3' v3_muscle tissue_pericyte","10x 3' v3_muscle tissue_endothelial cell of vascular tree","10x 3' v3_muscle tissue_macrophage","10x 3' v3_muscle tissue_mesenchymal stem cell","10x 3' v3_muscle tissue_capillary endothelial cell","10x 3' v3_muscle tissue_fast muscle cell","10x 3' v3_muscle tissue_slow muscle cell","Smart-seq2_muscle tissue_endothelial cell of vascular tree","Smart-seq2_muscle tissue_macrophage","Smart-seq2_muscle tissue_mesenchymal stem cell","10x 3' v3_rectus abdominis muscle_pericyte","10x 3' v3_rectus abdominis muscle_skeletal muscle satellite stem cell","10x 3' v3_rectus abdominis muscle_capillary endothelial cell","10x 3' v3_rectus abdominis muscle_endothelial cell of vascular tree","10x 3' v3_rectus abdominis muscle_macrophage","10x 3' v3_endocrine pancreas_endothelial cell","10x 3' v3_endocrine pancreas_pancreatic acinar cell","10x 3' v3_endocrine pancreas_pancreatic ductal cell","10x 3' v3_small intestine_intestinal crypt stem cell","10x 3' v3_small intestine_enterocyte","10x 3' v3_thymus_CD8-positive, alpha-beta T cell","10x 3' v3_thymus_memory B cell","10x 3' v3_thymus_naive B cell","10x 3' v3_thymus_fast muscle cell","10x 3' v3_thymus_thymocyte","Smart-seq2_thymus_fibroblast","10x 3' v3_trachea_connective tissue cell","10x 3' v3_aorta_fibroblast","10x 3' v3_aorta_macrophage","10x 3' v3_aorta_smooth muscle cell","10x 3' v3_aorta_endothelial cell","10x 3' v3_aorta_mature NK T cell","10x 3' v3_aorta_pericyte","10x 3' v3_aorta_mast cell","Smart-seq2_vasculature_fibroblast","10x 3' v2_islet of Langerhans_pancreatic A cell","10x 3' v2_islet of Langerhans_pancreatic D cell","10x 3' v2_islet of Langerhans_type B pancreatic cell","10x 3' v2_prostate gland_leukocyte","10x 3' v2_prostate gland_basal cell of prostate epithelium","10x 3' v2_prostate gland_seminal vesicle glandular cell","10x 3' v2_prostate gland_fibroblast of connective tissue of prostate","10x 3' v2_prostate gland_prostate gland microvascular endothelial cell","10x 3' v2_prostate gland_urethra urothelial cell","10x 3' v3_prostate gland_leukocyte","10x 3' v2_urethra_leukocyte","10x 3' v2_urethra_urethra urothelial cell","10x 3' v2_urethra_luminal cell of prostate epithelium","10x 3' v2_urethra_seminal vesicle glandular cell","10x 3' v2_urethra_fibroblast of connective tissue of prostate","10x 3' v2_urethra_prostate gland microvascular endothelial cell","10x 3' v2_urethra_basal cell of prostate epithelium","10x 3' v2_urethra_smooth muscle cell of prostate","10x 3' v3_urethra_urethra urothelial cell","10x 3' v3_urethra_seminal vesicle glandular cell","10x 3' v3_urethra_luminal cell of prostate epithelium","10x 3' v3_urethra_basal cell of prostate epithelium","10x 3' v3_urethra_leukocyte","10x 3' v3_urethra_fibroblast of connective tissue of prostate","10x 3' v3_urethra_prostate gland microvascular endothelial cell","10x 3' v2_PBMC_B cells","10x 3' v2_PBMC_CD14+ Monocytes","10x 3' v2_PBMC_CD4 T cells","10x 3' v2_PBMC_CD8 T cells","10x 3' v2_PBMC_FCGR3A+ Monocytes","10x 3' v2_PBMC_NK cells","10x 3' v2_PBMC_Dendritic cells","10x 3' v2_Atherosclerotic Plaque_T cell","10x 3' v2_Atherosclerotic Plaque_Macrophage","10x 3' v2_Atherosclerotic Plaque_NK","10x 3' v2_Atherosclerotic Plaque_Monocyte","10x 3' v2_Atherosclerotic Plaque_SMC","10x 3' v2_Atherosclerotic Plaque_B cell","10x 3' v2_Atherosclerotic Plaque_EC","10x 3' v2_Atherosclerotic Plaque_Fibroblast","10x 3' v2_Atherosclerotic Plaque_Fibromyocyte","10x 3' v2_Atherosclerotic Plaque_Mast cell","10x 3' v2_Atherosclerotic Plaque_DC","10x 3' v2_Atherosclerotic Plaque_Plasma cell"
    ]

    assays, tissues, _ = extract_and_filter(all_celltypes)

    # Create scatter plot
    with st.expander("General Parameters", expanded=True):
        study_type = st.radio(
            "Study type:",
            ["de", "eqtl"])
        organism = st.selectbox("Organisms", ["Homo sapiens", "Mus musculus"])
        selected_assay = st.selectbox("Assays", ["All"] + assays, key='assay', on_change=update_assay)

        _, tissues, _ = extract_and_filter(all_celltypes, assay_filter=selected_assay)
        selected_tissue = st.selectbox("Tissues", ["All"] + tissues, key='tissue')
        
        _, _, filtered_celltypes = extract_and_filter(all_celltypes, assay_filter=selected_assay, tissue_filter=selected_tissue)
        celltype = st.selectbox("Cell Types", filtered_celltypes)
    
    with st.expander("Advanced Options", expanded=False):
        col1, col2 = st.columns([3, 3])
        
        with col1:
            ct_freq_slider = st.slider("Cell Type Frequency", 0.0, 1.0, 0.1, step = 0.05, help="Frequency of the cell type of interest.")
            sample_size_ratio_slider = st.slider("Sample Size Ratio", 0.0, 50.0, 1.0, step = 0.05, help="ratio between sample size of group 0 (control group) and group 1 (Ratio=1 in case of balanced design)")
            ref_study = st.selectbox("Reference Study", ["Blueprint (CLL) iCLL-mCLL", "Blueprint (CLL) mCLL-uCLL", "Blueprint (CLL) uCLL-iCLL", "Moreno-Moral (Macrophages)", "Nicodemus-Johnson_AEC", "Pancreas_alphabeta", "Pancreas_ductacinar", "Custom"])
            total_budget = st.slider("Total Budget", step=500,min_value =0,value = 50000, help="The total budget available for the sequencing")
        
        with col2:
            parameter_grid = st.selectbox("Parameter Grid", ["samples - cells per sample", "samples - reads per cell", "cells per sample - reads per cell"])
            rangeX_min = st.slider("Sample size (min)", value=10, step=1, help="Minimal value of the tested ranges for the parameter on the x-Axis.")
            rangeX_max = st.slider("Sample size (max)", value=50, step=1, help="Maximum value of the tested ranges for the parameter on the x-Axis.")
            
            rangeY_min = st.slider("Cells (min)",value=2000, step=1),
            rangeY_max = st.slider("Cells (max)",value=10000, step=1),
            
            steps = st.slider("Steps", min_value=0, value=5, step=1, help= "number of values in the parameter ranges for the parameter grid")

    with st.expander("Cost and Experimental Parameters", expanded=False):
        col1, col2 = st.columns([3, 3])
        with col1:
            cost_10x_kit = st.slider("Cost 10X kit", value = 5600, step=100,min_value=0, help="Cost for one 10X Genomics kit")     
            cost_flow_cell = st.slider("Cost Flow Cell", value = 14032, step=100,min_value=0, help="Cost for one flow cell")
            reads_per_flow_cell = st.slider("Number of reads per flow cell", value = 4100000000, step=10000,min_value=0)   
            cells_per_lane = st.slider("Cells per lane", value = 8000, step=500,min_value=0, help="Number of cells meassured on one 10X lane (dependent on the parameter \"Reactions Per Kit\")")
            
        with col2: 
            reactions_per_kit = st.slider("Reactions Per Kit", value = 6, step = 1, min_value= 1, help="Number of reactions/lanes on one 10X kit (different kit versions possible)")
            p_value = st.slider("P-value", value=0.05,step=0.01,min_value=0.0,max_value=1.0, help="Significance threshold")
            multiple_testing_method = st.selectbox("Multiple testing method", ["FDR", "FWER", "None"])
            indepsnps = st.slider("Independent SNPs", value=10, min_value=1, step=1),
    
    with st.expander("Mapping and Multiplet estimation", expanded=False):
        col1, col2 = st.columns([3, 3])
        with col1:
            mapping_efficiency = st.slider("Mapping efficiency", value = 0.8,step=0.05,min_value=0.0,max_value=1.0)
            multiplet_rate = st.slider("Multiplet Rate", value = 7.67e-06,step=1e-6,min_value=0.0, help="Rate factor to calculate the number of multiplets dependent on the number of cells loaded per lane. We assume a linear relationship of multiplet fraction = cells per lane * multiplet rate.")
            multiplet_factor = st.slider("Multiplet Factor", value = 1.82, step=0.1,min_value=1.0, help="Multiplets have a higher fraction of reads per cell than singlets, the multiplet factor shows the ratio between the reads.")
        
        with col2:
            min_num_UMI_per_gene = st.slider("Minimal number of UMI per gene", value = 3, step=1,min_value=1)
            fraction_of_indiv = st.slider("Fraction of individuals", value = 0.5,step=0.05,min_value=0.0,max_value=1.0)
            skip_power = st.checkbox("Skip power for lowly expressed genes", value=False)
            use_simulated = st.checkbox("Use simulated power for eQTLs", value=False)

    rangeX = np.round(np.linspace(rangeX_min, rangeX_max, steps)).astype(int)
    rangeY = np.round(np.linspace(rangeY_min[0], rangeY_max[0], steps)).astype(int)

    selected_pair = parameter_grid

    if selected_pair == "samples - cells per sample":
        sample_range = rangeX
        cells_range = rangeY
        read_range = None
    elif selected_pair == "samples - reads per cell":
        sample_range = rangeX
        cells_range = None
        read_range = rangeY
    else:  # "cells per sample - reads per cell"
        sample_range = None
        cells_range = rangeX
        read_range = rangeY
    
    args = {
        "totalBudget" : total_budget,
        "type" : study_type,
        "ct" : celltype, 
        "ct.freq" : ct_freq_slider,
        "costKit" : cost_10x_kit,
        "costFlowCell" : cost_flow_cell,
        "readsPerFlowcell" : reads_per_flow_cell,
        "ref.study.name" : ref_study,
        "cellsPerLane" : cells_per_lane,
        "nSamplesRange" : sample_range.tolist() if sample_range is not None else None,
        "nCellsRange" : cells_range.tolist() if cells_range is not None else None,
        "readDepthRange" : read_range.tolist() if read_range is not None else None,
        "mappingEfficiency" : mapping_efficiency,
        "multipletRate" : multiplet_rate,
        "multipletFactor" : multiplet_factor,
        "min.UMI.counts" : min_num_UMI_per_gene,
        "perc.indiv.expr" : fraction_of_indiv,
        "samplingMethod" : "quantiles",
        "sign.threshold" : p_value,
        "MTmethod" : multiple_testing_method,
        "useSimulatedPower" : use_simulated,
        "speedPowerCalc" : skip_power,
        "indepSNPs" : indepsnps,
        "ssize.ratio.de" : sample_size_ratio_slider,
        "reactionsPerKit" : reactions_per_kit
    }

    args = json_safe(args)
    
    if st.button("Run analysis"):
        
        args_json = json.dumps(args)

        logging.debug(f"JSON string: {args_json}")

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            json.dump(args, temp_file)
            temp_file_path = temp_file.name

        result = subprocess.run(['Rscript', 'scpower_collector.R', temp_file_path], capture_output=True, text=True)

        logging.info(f"R script stdout: {result.stdout}")
        if result.stderr:
            logging.error(f"R script stderr: {result.stderr}")

        # Remove the temporary file
        os.unlink(temp_file_path)

        st.session_state.scatter_data = json.loads(result.stdout)
        st.session_state.influence_data = json.loads(result.stdout)


        
        st.markdown("<br>", unsafe_allow_html=True)

        # data shown as json as well
        if isinstance(st.session_state.scatter_data, list):
            st.write(f"Data in json format ({len(st.session_state.scatter_data)} items):")
        st.json(st.session_state.scatter_data, expanded=False)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("""
        <div class="hover-text">
            <h3>Scatter Plot</h3>
            <div class="hover-content">
                <p>Detection power depending on <em>cells per individual</em>, <em>read depth</em> and <em>sample size</em>.</p>
                <p><strong>How to use this scatter plot:</strong></p>
                <ul style="padding-left: 20px;">
                    <li>Select the variables for X-axis, Y-axis, and Size from the dropdowns below.</li>
                    <li>The plot will update automatically based on your selections.</li>
                    <li>Use the plot tools to zoom, pan, or save the image.</li>
                </ul>
                <p><em>Tip: Try different combinations to discover interesting patterns in your data!</em></p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        keys = sorted(st.session_state.scatter_data[0].keys())

        x_axis = st.selectbox("Select X-axis", options=keys, index=keys.index("sampleSize"))
        y_axis = st.selectbox("Select Y-axis", options=keys, index=keys.index("totalCells"))
        size_axis = st.selectbox("Select Size-axis", options=keys, index=keys.index("Detection.power"))

        fig = create_scatter_plot(st.session_state.scatter_data, x_axis, y_axis, size_axis)
        if fig is not None:
            st.plotly_chart(fig)
            st.session_state.success_message.empty() # clear the success messages shown in the UI

        # Add the new influence plot
        if st.session_state.influence_data is not None:

            st.markdown("""
            <div class="hover-text">
                <h3>Influence Plot</h3>
                <div class="hover-content">
                    <ul>
                        <li>The overall detection power is the result of expression probability (probability that the DE/eQTL genes are detected) and DE power (probability that the DE/eQTL genes are found significant).</p>
                        <li>The plots show the influence of the y axis (left) and x axis (right) parameter of the upper plot onto the power of the selected study, while keeping the second parameter constant.</p>
                        <li>The dashed lines shows the location of the selected study.</p>
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)

            parameter_vector = ["sc", 1000, 100, 200, 400000000, "eqtl"]
            fig = create_influence_plot(st.session_state.influence_data, parameter_vector)
            if fig is not None:
                st.plotly_chart(fig)
        else:
            st.warning("No influence data available. Please check your data source.")

def main():
    st.set_page_config(initial_sidebar_state="collapsed")
    
    if 'page' not in st.session_state:
        st.session_state.page = "Home"

    st.sidebar.title("Navigation")
    pages = ["Home", "Description", "Detect DE/eQTL Genes", "Detect Cell Types", "License Statement"]
    page = st.sidebar.radio("", pages, index=pages.index(st.session_state.page))

    if page != st.session_state.page:
        st.session_state.page = page
        st.rerun()

    if st.session_state.page == "Home":
        show_home_page()
    elif st.session_state.page == "Description":
        show_description_page()
    elif st.session_state.page == "Detect DE/eQTL Genes":
        perform_analysis()
    elif st.session_state.page == "License Statement":
        show_license_page()      

if __name__ == "__main__":
    main()