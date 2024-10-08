import streamlit as st
import json
import time
import os
import plotly.graph_objects as go
import plotly.subplots as sp
import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
from io import BytesIO

from home import show_home_page
from description import show_description_page
from license import show_license_page

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

def perform_analysis():
    st.title("Detect DE/eQTL genes")
    scatter_file_id   = "1NkBP3AzLWuXKeYwgtVdTYxrzLjCuqLkR"
    influence_file_id = "1viAH5OEyhSoQjdGHi2Cm0_tFHrr1Z3GQ"

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

    # Fetch initial data if not already present
    if st.session_state.scatter_data is None:
        st.session_state.scatter_data = read_json_file("./scPower_shiny/power_study_plot.json")
    if st.session_state.influence_data is None:
        st.session_state.influence_data = read_json_file("./scPower_shiny/power_study.json")

    # Create scatter plot
    if isinstance(st.session_state.scatter_data, list) and len(st.session_state.scatter_data) > 0:
        with st.expander("General Parameters", expanded=True):
            study_type = st.radio(
                "Study type:",
                ["DE Study", "eQTL Study"])
            organism = st.selectbox("Organisms", ["Homo sapiens", "Mus musculus"])
            assay = st.selectbox("Assays", ["10x 3' v2", "10x 3' v3", "Smart-seq2", "10x 5' v1", "10x 5' v2" ])
            tissue = st.selectbox("Tissues", sorted(["PBMC"                            ,"lingula of left lung",
                                            "prostate gland"                  ,"lamina propria",
                                            "vasculature"                     ,"limb muscle",
                                            "urethra"                         ,"blood",
                                            "gastrocnemius"                   ,"breast",
                                            "mucosa"                          ,"esophagus muscularis mucosa",
                                            "anterior wall of left ventricle" ,"skin of leg",
                                            "ileum"                           ,"lung",
                                            "thoracic lymph node"             ,"mesenteric lymph node",
                                            "bone marrow"                     ,"skeletal muscle tissue",
                                            "liver"                           ,"spleen",
                                            "omentum"                         ,"caecum",
                                            "thymus"                          ,"duodenum",
                                            "transverse colon"                ,"jejunal epithelium",
                                            "trachea"                         ,"inguinal lymph node",
                                            "lymph node"                      ,"parotid gland",
                                            "anterior part of tongue"         ,"posterior part of tongue",
                                            "mammary gland"                   ,"endometrium",
                                            "myometrium"                      ,"eye",
                                            "conjunctiva"                     ,"adipose tissue",
                                            "subcutaneous adipose tissue"     ,"skin of body",
                                            "cardiac atrium"                  ,"cardiac ventricle",
                                            "exocrine pancreas"               ,"skin of abdomen",
                                            "skin of chest"                   ,"uterus",
                                            "muscle of pelvic diaphragm"      ,"submandibular gland",
                                            "cornea"                          ,"retinal neural layer",
                                            "sclera"                          ,"bladder organ",
                                            "large intestine"                 ,"small intestine",
                                            "muscle of abdomen"               ,"coronary artery",
                                            "kidney"                          ,"muscle tissue",
                                            "rectus abdominis muscle"         ,"endocrine pancreas",
                                            "aorta"                           ,"islet of Langerhans"]))
            celltype = st.selectbox("Cell Types", sorted(["10x 3' v2_PBMC_B cells","10x 3' v2_PBMC_CD14+        Monocytes","10x 3' v2_PBMC_CD4 T cells","10x 3' v2_PBMC_CD8 T cells","10x 3' v2_PBMC_FCGR3A+ Monocytes","10x 3' v2_PBMC_NK cells","10x 3' v2_PBMC_Dendritic cells","10x 3' v2_PBMC_B cells","T cell (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Macrophage (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","NK (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Monocyte (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","SMC (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","B cell (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","EC (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Fibroblast (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Fibromyocyte (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Mast cell (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","DC (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","Plasma cell (Assay: 10x 3' v2, Tissue: Atherosclerotic Plaque)","macrophage (Assay: 10x 3' v2, Tissue: lingula of left lung)","epithelial cell of prostate (Assay: 10x 3' v2, Tissue: prostate gland)","lymphocyte (Assay: 10x 3' v3, Tissue: lamina propria)","macrophage (Assay: 10x 3' v3, Tissue: prostate gland)","fibroblast (Assay: Smart-seq2, Tissue: vasculature)","luminal cell of prostate epithelium (Assay: 10x 3' v2, Tissue: prostate gland)","smooth muscle cell of prostate (Assay: 10x 3' v2, Tissue: prostate gland)","macrophage (Assay: 10x 3' v2, Tissue: limb muscle)","endothelial cell (Assay: 10x 3' v2, Tissue: limb muscle)","mesenchymal stem cell (Assay: 10x 3' v2, Tissue: limb muscle)","smooth muscle cell (Assay: 10x 3' v2, Tissue: limb muscle)","Schwann cell (Assay: 10x 3' v2, Tissue: limb muscle)","skeletal muscle satellite cell (Assay: 10x 3' v2, Tissue: limb muscle)","B cell (Assay: 10x 3' v2, Tissue: limb muscle)","cell of skeletal muscle (Assay: 10x 3' v2, Tissue: limb muscle)","T cell (Assay: 10x 3' v2, Tissue: limb muscle)","luminal cell of prostate epithelium (Assay: 10x 3' v3, Tissue: prostate gland)","leukocyte (Assay: 10x 3' v2, Tissue: prostate gland)","basal cell of prostate epithelium (Assay: 10x 3' v2, Tissue: prostate gland)","seminal vesicle glandular cell (Assay: 10x 3' v2, Tissue: prostate gland)","fibroblast of connective tissue of prostate (Assay: 10x 3' v2, Tissue: prostate gland)","prostate gland microvascular endothelial cell (Assay: 10x 3' v2, Tissue: prostate gland)","urethra urothelial cell (Assay: 10x 3' v2, Tissue: prostate gland)","leukocyte (Assay: 10x 3' v3, Tissue: prostate gland)","leukocyte (Assay: 10x 3' v2, Tissue: urethra)","urethra urothelial cell (Assay: 10x 3' v2, Tissue: urethra)","luminal cell of prostate epithelium (Assay: 10x 3' v2, Tissue: urethra)","seminal vesicle glandular cell (Assay: 10x 3' v2, Tissue: urethra)","fibroblast of connective tissue of prostate (Assay: 10x 3' v2, Tissue: urethra)","prostate gland microvascular endothelial cell (Assay: 10x 3' v2, Tissue: urethra)","basal cell of prostate epithelium (Assay: 10x 3' v2, Tissue: urethra)","smooth muscle cell of prostate (Assay: 10x 3' v2, Tissue: urethra)","urethra urothelial cell (Assay: 10x 3' v3, Tissue: urethra)","seminal vesicle glandular cell (Assay: 10x 3' v3, Tissue: urethra)","luminal cell of prostate epithelium (Assay: 10x 3' v3, Tissue: urethra)","basal cell of prostate epithelium (Assay: 10x 3' v3, Tissue: urethra)","leukocyte (Assay: 10x 3' v3, Tissue: urethra)","fibroblast of connective tissue of prostate (Assay: 10x 3' v3, Tissue: urethra)","prostate gland microvascular endothelial cell (Assay: 10x 3' v3, Tissue: urethra)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v1, Tissue: blood)","naive B cell (Assay: 10x 5' v1, Tissue: blood)","plasmacytoid dendritic cell (Assay: 10x 5' v1, Tissue: blood)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: blood)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: blood)","CD14-low, CD16-positive monocyte (Assay: 10x 5' v1, Tissue: blood)","CD14-positive monocyte (Assay: 10x 5' v1, Tissue: blood)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: blood)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: blood)","mature NK T cell (Assay: 10x 5' v1, Tissue: blood)","memory B cell (Assay: 10x 5' v1, Tissue: blood)","mucosal invariant T cell (Assay: 10x 5' v1, Tissue: blood)","T cell (Assay: 10x 5' v1, Tissue: blood)","natural killer cell (Assay: 10x 5' v1, Tissue: blood)","regulatory T cell (Assay: 10x 5' v1, Tissue: blood)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: blood)","platelet (Assay: 10x 5' v1, Tissue: blood)","plasma cell (Assay: 10x 5' v1, Tissue: blood)","B cell (Assay: 10x 5' v1, Tissue: blood)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: blood)","plasmablast (Assay: 10x 5' v1, Tissue: blood)","erythrocyte (Assay: 10x 5' v1, Tissue: blood)","hematopoietic stem cell (Assay: 10x 5' v1, Tissue: blood)","slow muscle cell (Assay: 10x 3' v2, Tissue: gastrocnemius)","skeletal muscle fiber (Assay: 10x 3' v2, Tissue: gastrocnemius)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: gastrocnemius)","skeletal muscle fibroblast (Assay: 10x 3' v2, Tissue: gastrocnemius)","fast muscle cell (Assay: 10x 3' v2, Tissue: gastrocnemius)","luminal epithelial cell of mammary gland (Assay: 10x 3' v2, Tissue: breast)","subcutaneous fat cell (Assay: 10x 3' v2, Tissue: breast)","macrophage (Assay: 10x 3' v2, Tissue: breast)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: breast)","squamous epithelial cell (Assay: 10x 3' v2, Tissue: mucosa)","basal cell (Assay: 10x 3' v2, Tissue: mucosa)","myoepithelial cell of mammary gland (Assay: 10x 3' v2, Tissue: mucosa)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: mucosa)","basal epithelial cell of tracheobronchial tree (Assay: 10x 3' v2, Tissue: mucosa)","glandular epithelial cell (Assay: 10x 3' v2, Tissue: mucosa)","fibroblast (Assay: 10x 3' v2, Tissue: mucosa)","endothelial cell of lymphatic vessel (Assay: 10x 3' v2, Tissue: mucosa)","contractile cell (Assay: 10x 3' v2, Tissue: mucosa)","macrophage (Assay: 10x 3' v2, Tissue: mucosa)","T cell (Assay: 10x 3' v2, Tissue: mucosa)","smooth muscle cell (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","enteric smooth muscle cell (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","endothelial cell of lymphatic vessel (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","fibroblast (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","macrophage (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","mast cell (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","fat cell (Assay: 10x 3' v2, Tissue: esophagus muscularis mucosa)","cardiac muscle cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","fibroblast (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","contractile cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","macrophage (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","subcutaneous fat cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","professional antigen presenting cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","T cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","fibroblast of cardiac tissue (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","cardiac endothelial cell (Assay: 10x 3' v2, Tissue: anterior wall of left ventricle)","epithelial cell of alveolus of lung (Assay: 10x 3' v2, Tissue: lingula of left lung)","respiratory basal cell (Assay: 10x 3' v2, Tissue: lingula of left lung)","alveolar macrophage (Assay: 10x 3' v2, Tissue: lingula of left lung)","bronchial epithelial cell (Assay: 10x 3' v2, Tissue: lingula of left lung)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: lingula of left lung)","fibroblast (Assay: 10x 3' v2, Tissue: lingula of left lung)","endothelial cell of lymphatic vessel (Assay: 10x 3' v2, Tissue: lingula of left lung)","basal epithelial cell of prostatic duct (Assay: 10x 3' v2, Tissue: prostate gland)","skin fibroblast (Assay: 10x 3' v2, Tissue: prostate gland)","endothelial cell of vascular tree (Assay: 10x 3' v2, Tissue: prostate gland)","macrophage (Assay: 10x 3' v2, Tissue: prostate gland)","endothelial cell of lymphatic vessel (Assay: 10x 3' v2, Tissue: prostate gland)","epithelial cell of sweat gland (Assay: 10x 3' v2, Tissue: skin of leg)","basal cell of epidermis (Assay: 10x 3' v2, Tissue: skin of leg)","sebaceous gland cell (Assay: 10x 3' v2, Tissue: skin of leg)","keratinocyte (Assay: 10x 3' v2, Tissue: skin of leg)","skin fibroblast (Assay: 10x 3' v2, Tissue: skin of leg)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: ileum)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: ileum)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: ileum)","memory B cell (Assay: 10x 5' v1, Tissue: ileum)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: lung)","macrophage (Assay: 10x 5' v1, Tissue: lung)","alveolar macrophage (Assay: 10x 5' v1, Tissue: lung)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: lung)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: lung)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: lung)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: lung)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: lung)","classical monocyte (Assay: 10x 5' v1, Tissue: lung)","mast cell (Assay: 10x 5' v1, Tissue: lung)","non-classical monocyte (Assay: 10x 5' v1, Tissue: lung)","animal cell (Assay: 10x 5' v1, Tissue: lung)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","naive B cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","classical monocyte (Assay: 10x 5' v1, Tissue: thoracic lymph node)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: thoracic lymph node)","memory B cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","regulatory T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v1, Tissue: thoracic lymph node)","T follicular helper cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","plasma cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","alpha-beta T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","macrophage (Assay: 10x 5' v1, Tissue: thoracic lymph node)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","germinal center B cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","mucosal invariant T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","alveolar macrophage (Assay: 10x 5' v1, Tissue: thoracic lymph node)","dendritic cell, human (Assay: 10x 5' v1, Tissue: thoracic lymph node)","group 3 innate lymphoid cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","lymphocyte (Assay: 10x 5' v1, Tissue: thoracic lymph node)","animal cell (Assay: 10x 5' v1, Tissue: thoracic lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","naive B cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","memory B cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","T follicular helper cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","regulatory T cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","lymphocyte (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","germinal center B cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","group 3 innate lymphoid cell (Assay: 10x 5' v1, Tissue: mesenteric lymph node)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: bone marrow)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: bone marrow)","classical monocyte (Assay: 10x 5' v1, Tissue: bone marrow)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: bone marrow)","erythroid lineage cell (Assay: 10x 5' v1, Tissue: bone marrow)","animal cell (Assay: 10x 5' v1, Tissue: bone marrow)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: bone marrow)","mucosal invariant T cell (Assay: 10x 5' v1, Tissue: bone marrow)","progenitor cell (Assay: 10x 5' v1, Tissue: bone marrow)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: bone marrow)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: bone marrow)","naive B cell (Assay: 10x 5' v1, Tissue: bone marrow)","megakaryocyte (Assay: 10x 5' v1, Tissue: bone marrow)","memory B cell (Assay: 10x 5' v1, Tissue: bone marrow)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: bone marrow)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v1, Tissue: bone marrow)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: bone marrow)","non-classical monocyte (Assay: 10x 5' v1, Tissue: bone marrow)","lymphocyte (Assay: 10x 5' v1, Tissue: bone marrow)","plasmacytoid dendritic cell (Assay: 10x 5' v1, Tissue: bone marrow)","regulatory T cell (Assay: 10x 5' v1, Tissue: bone marrow)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","classical monocyte (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: liver)","mucosal invariant T cell (Assay: 10x 5' v1, Tissue: liver)","macrophage (Assay: 10x 5' v1, Tissue: liver)","classical monocyte (Assay: 10x 5' v1, Tissue: liver)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v1, Tissue: liver)","naive B cell (Assay: 10x 5' v1, Tissue: liver)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: liver)","animal cell (Assay: 10x 5' v1, Tissue: liver)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: liver)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: liver)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: liver)","non-classical monocyte (Assay: 10x 5' v1, Tissue: liver)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: liver)","plasma cell (Assay: 10x 5' v1, Tissue: liver)","memory B cell (Assay: 10x 5' v1, Tissue: liver)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: spleen)","memory B cell (Assay: 10x 5' v1, Tissue: spleen)","naive B cell (Assay: 10x 5' v1, Tissue: spleen)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: spleen)","regulatory T cell (Assay: 10x 5' v1, Tissue: spleen)","animal cell (Assay: 10x 5' v1, Tissue: spleen)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: spleen)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: spleen)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: spleen)","mucosal invariant T cell (Assay: 10x 5' v1, Tissue: spleen)","macrophage (Assay: 10x 5' v1, Tissue: spleen)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: spleen)","classical monocyte (Assay: 10x 5' v1, Tissue: spleen)","T follicular helper cell (Assay: 10x 5' v1, Tissue: spleen)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v1, Tissue: spleen)","conventional dendritic cell (Assay: 10x 5' v1, Tissue: spleen)","non-classical monocyte (Assay: 10x 5' v1, Tissue: spleen)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v1, Tissue: spleen)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: spleen)","plasma cell (Assay: 10x 5' v1, Tissue: spleen)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: spleen)","lymphocyte (Assay: 10x 5' v1, Tissue: spleen)","plasmablast (Assay: 10x 5' v1, Tissue: spleen)","germinal center B cell (Assay: 10x 5' v1, Tissue: spleen)","memory B cell (Assay: 10x 5' v1, Tissue: omentum)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: omentum)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: omentum)","lymphocyte (Assay: 10x 5' v1, Tissue: liver)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: liver)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: liver)","gamma-delta T cell (Assay: 10x 5' v1, Tissue: caecum)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: caecum)","plasma cell (Assay: 10x 5' v1, Tissue: caecum)","plasma cell (Assay: 10x 5' v1, Tissue: bone marrow)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: thymus)","memory B cell (Assay: 10x 5' v1, Tissue: thymus)","CD4-positive helper T cell (Assay: 10x 5' v1, Tissue: duodenum)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v1, Tissue: duodenum)","alpha-beta T cell (Assay: 10x 5' v1, Tissue: duodenum)","classical monocyte (Assay: 10x 5' v1, Tissue: blood)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: blood)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v1, Tissue: blood)","non-classical monocyte (Assay: 10x 5' v1, Tissue: blood)","megakaryocyte (Assay: 10x 5' v1, Tissue: blood)","lymphocyte (Assay: 10x 5' v1, Tissue: blood)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v1, Tissue: blood)","memory B cell (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","non-classical monocyte (Assay: 10x 5' v1, Tissue: skeletal muscle tissue)","plasma cell (Assay: 10x 5' v1, Tissue: transverse colon)","naive B cell (Assay: 10x 5' v2, Tissue: spleen)","T follicular helper cell (Assay: 10x 5' v2, Tissue: spleen)","mucosal invariant T cell (Assay: 10x 5' v2, Tissue: spleen)","memory B cell (Assay: 10x 5' v2, Tissue: spleen)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: spleen)","regulatory T cell (Assay: 10x 5' v2, Tissue: spleen)","classical monocyte (Assay: 10x 5' v2, Tissue: spleen)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v2, Tissue: spleen)","conventional dendritic cell (Assay: 10x 5' v2, Tissue: spleen)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v2, Tissue: spleen)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: spleen)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: spleen)","germinal center B cell (Assay: 10x 5' v2, Tissue: spleen)","memory B cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: spleen)","animal cell (Assay: 10x 5' v2, Tissue: spleen)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: spleen)","macrophage (Assay: 10x 5' v2, Tissue: spleen)","lymphocyte (Assay: 10x 5' v2, Tissue: spleen)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v2, Tissue: spleen)","alpha-beta T cell (Assay: 10x 5' v2, Tissue: spleen)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: spleen)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: spleen)","regulatory T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","naive B cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","non-classical monocyte (Assay: 10x 5' v2, Tissue: spleen)","plasma cell (Assay: 10x 5' v2, Tissue: spleen)","animal cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","group 3 innate lymphoid cell (Assay: 10x 5' v2, Tissue: spleen)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","T follicular helper cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","group 3 innate lymphoid cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","lymphocyte (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: lamina propria)","regulatory T cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","lymphocyte (Assay: 10x 5' v2, Tissue: thoracic lymph node)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: thoracic lymph node)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v2, Tissue: lamina propria)","memory B cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: lamina propria)","T follicular helper cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: thoracic lymph node)","naive B cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v2, Tissue: thoracic lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","naive B cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","plasma cell (Assay: 10x 5' v2, Tissue: lamina propria)","plasma cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: jejunal epithelium)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: jejunal epithelium)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","macrophage (Assay: 10x 5' v2, Tissue: lamina propria)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: lamina propria)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","mucosal invariant T cell (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v2, Tissue: bone marrow)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: bone marrow)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: bone marrow)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: bone marrow)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: bone marrow)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: bone marrow)","regulatory T cell (Assay: 10x 5' v2, Tissue: bone marrow)","erythroid lineage cell (Assay: 10x 5' v2, Tissue: bone marrow)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v2, Tissue: blood)","naive B cell (Assay: 10x 5' v2, Tissue: bone marrow)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: blood)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: bone marrow)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: bone marrow)","mucosal invariant T cell (Assay: 10x 5' v2, Tissue: bone marrow)","memory B cell (Assay: 10x 5' v2, Tissue: bone marrow)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: blood)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: blood)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v2, Tissue: bone marrow)","animal cell (Assay: 10x 5' v2, Tissue: bone marrow)","classical monocyte (Assay: 10x 5' v2, Tissue: bone marrow)","progenitor cell (Assay: 10x 5' v2, Tissue: bone marrow)","non-classical monocyte (Assay: 10x 5' v2, Tissue: bone marrow)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: mesenteric lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 5' v2, Tissue: liver)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 5' v2, Tissue: liver)","gamma-delta T cell (Assay: 10x 5' v2, Tissue: liver)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 5' v2, Tissue: liver)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 5' v2, Tissue: liver)","mucosal invariant T cell (Assay: 10x 5' v2, Tissue: liver)","CD4-positive helper T cell (Assay: 10x 5' v2, Tissue: liver)","classical monocyte (Assay: 10x 5' v2, Tissue: liver)","non-classical monocyte (Assay: 10x 5' v2, Tissue: liver)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 5' v2, Tissue: liver)","alveolar macrophage (Assay: 10x 5' v2, Tissue: lung)","CD8-positive, alpha-beta memory T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","alpha-beta T cell (Assay: 10x 5' v2, Tissue: jejunal epithelium)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: lamina propria)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: lung)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 3' v3, Tissue: bone marrow)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: jejunal epithelium)","classical monocyte (Assay: 10x 3' v3, Tissue: blood)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 3' v3, Tissue: spleen)","mucosal invariant T cell (Assay: 10x 3' v3, Tissue: spleen)","alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 3' v3, Tissue: blood)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","classical monocyte (Assay: 10x 3' v3, Tissue: bone marrow)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 3' v3, Tissue: spleen)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 3' v3, Tissue: spleen)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: jejunal epithelium)","animal cell (Assay: 10x 3' v3, Tissue: bone marrow)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 3' v3, Tissue: lung)","regulatory T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","memory B cell (Assay: 10x 3' v3, Tissue: spleen)","plasmablast (Assay: 10x 3' v3, Tissue: spleen)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: lamina propria)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lung)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: jejunal epithelium)","memory B cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: spleen)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","classical monocyte (Assay: 10x 3' v3, Tissue: lung)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: lamina propria)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","naive B cell (Assay: 10x 3' v3, Tissue: bone marrow)","mast cell (Assay: 10x 3' v3, Tissue: lung)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: spleen)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","T follicular helper cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 3' v3, Tissue: blood)","naive B cell (Assay: 10x 3' v3, Tissue: spleen)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: spleen)","classical monocyte (Assay: 10x 3' v3, Tissue: spleen)","mast cell (Assay: 10x 3' v3, Tissue: lamina propria)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 3' v3, Tissue: bone marrow)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: spleen)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 3' v3, Tissue: lung)","progenitor cell (Assay: 10x 3' v3, Tissue: bone marrow)","lymphocyte (Assay: 10x 3' v3, Tissue: blood)","lymphocyte (Assay: 10x 3' v3, Tissue: bone marrow)","regulatory T cell (Assay: 10x 3' v3, Tissue: bone marrow)","memory B cell (Assay: 10x 3' v3, Tissue: bone marrow)","CD16-positive, CD56-dim natural killer cell, human (Assay: 10x 3' v3, Tissue: lung)","lymphocyte (Assay: 10x 3' v3, Tissue: spleen)","effector memory CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","non-classical monocyte (Assay: 10x 3' v3, Tissue: bone marrow)","T follicular helper cell (Assay: 10x 3' v3, Tissue: spleen)","regulatory T cell (Assay: 10x 3' v3, Tissue: spleen)","group 3 innate lymphoid cell (Assay: 10x 3' v3, Tissue: spleen)","alveolar macrophage (Assay: 10x 3' v3, Tissue: lung)","erythroid lineage cell (Assay: 10x 3' v3, Tissue: bone marrow)","regulatory T cell (Assay: 10x 3' v3, Tissue: lung)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 3' v3, Tissue: bone marrow)","plasma cell (Assay: 10x 3' v3, Tissue: spleen)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: spleen)","lymphocyte (Assay: 10x 3' v3, Tissue: thoracic lymph node)","CD16-negative, CD56-bright natural killer cell, human (Assay: 10x 3' v3, Tissue: thoracic lymph node)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: bone marrow)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 3' v3, Tissue: thoracic lymph node)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","conventional dendritic cell (Assay: 10x 3' v3, Tissue: bone marrow)","macrophage (Assay: 10x 3' v3, Tissue: lamina propria)","conventional dendritic cell (Assay: 10x 3' v3, Tissue: lung)","conventional dendritic cell (Assay: 10x 3' v3, Tissue: lamina propria)","plasmacytoid dendritic cell (Assay: 10x 3' v3, Tissue: bone marrow)","naive B cell (Assay: 10x 3' v3, Tissue: lung)","regulatory T cell (Assay: 10x 3' v3, Tissue: blood)","plasma cell (Assay: 10x 3' v3, Tissue: lamina propria)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 3' v3, Tissue: blood)","plasmablast (Assay: 10x 3' v3, Tissue: bone marrow)","T follicular helper cell (Assay: 10x 3' v3, Tissue: blood)","non-classical monocyte (Assay: 10x 3' v3, Tissue: lung)","alpha-beta T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 3' v3, Tissue: spleen)","plasma cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","animal cell (Assay: 10x 3' v3, Tissue: blood)","progenitor cell (Assay: 10x 3' v3, Tissue: blood)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 3' v3, Tissue: bone marrow)","lymphocyte (Assay: 10x 3' v3, Tissue: lung)","macrophage (Assay: 10x 3' v3, Tissue: lung)","progenitor cell (Assay: 10x 3' v3, Tissue: spleen)","naive B cell (Assay: 10x 3' v3, Tissue: blood)","animal cell (Assay: 10x 3' v3, Tissue: lung)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lung)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: spleen)","naive B cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","group 3 innate lymphoid cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","mast cell (Assay: 10x 3' v3, Tissue: spleen)","dendritic cell, human (Assay: 10x 3' v3, Tissue: lung)","T follicular helper cell (Assay: 10x 3' v3, Tissue: bone marrow)","plasmacytoid dendritic cell (Assay: 10x 3' v3, Tissue: spleen)","mucosal invariant T cell (Assay: 10x 3' v3, Tissue: lung)","mucosal invariant T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: lung)","mast cell (Assay: 10x 3' v3, Tissue: bone marrow)","plasmablast (Assay: 10x 3' v3, Tissue: thoracic lymph node)","effector memory CD8-positive, alpha-beta T cell, terminally differentiated (Assay: 10x 3' v3, Tissue: lung)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","animal cell (Assay: 10x 3' v3, Tissue: spleen)","plasma cell (Assay: 10x 3' v3, Tissue: bone marrow)","CD8-positive, alpha-beta memory T cell, CD45RO-positive (Assay: 10x 3' v3, Tissue: blood)","conventional dendritic cell (Assay: 10x 3' v3, Tissue: blood)","mast cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","mucosal invariant T cell (Assay: 10x 3' v3, Tissue: bone marrow)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","gamma-delta T cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","memory B cell (Assay: 10x 3' v3, Tissue: blood)","animal cell (Assay: 10x 3' v3, Tissue: thoracic lymph node)","T follicular helper cell (Assay: 10x 3' v3, Tissue: lung)","animal cell (Assay: 10x 3' v3, Tissue: lamina propria)","mast cell (Assay: 10x 3' v3, Tissue: jejunal epithelium)","macrophage (Assay: 10x 3' v3, Tissue: liver)","monocyte (Assay: 10x 3' v3, Tissue: liver)","endothelial cell of hepatic sinusoid (Assay: 10x 3' v3, Tissue: liver)","mature NK T cell (Assay: 10x 3' v3, Tissue: liver)","hepatocyte (Assay: 10x 3' v3, Tissue: liver)","macrophage (Assay: 10x 3' v3, Tissue: trachea)","tracheal goblet cell (Assay: 10x 3' v3, Tissue: trachea)","fibroblast (Assay: 10x 3' v3, Tissue: trachea)","endothelial cell (Assay: 10x 3' v3, Tissue: trachea)","smooth muscle cell (Assay: 10x 3' v3, Tissue: trachea)","ciliated cell (Assay: 10x 3' v3, Tissue: trachea)","secretory cell (Assay: 10x 3' v3, Tissue: trachea)","T cell (Assay: 10x 3' v3, Tissue: trachea)","mast cell (Assay: 10x 3' v3, Tissue: trachea)","plasma cell (Assay: 10x 3' v3, Tissue: trachea)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: trachea)","B cell (Assay: 10x 3' v3, Tissue: trachea)","neutrophil (Assay: 10x 3' v3, Tissue: trachea)","erythrocyte (Assay: 10x 3' v3, Tissue: blood)","CD4-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: blood)","CD8-positive, alpha-beta cytokine secreting effector T cell (Assay: 10x 3' v3, Tissue: blood)","neutrophil (Assay: 10x 3' v3, Tissue: blood)","mature NK T cell (Assay: 10x 3' v3, Tissue: blood)","type I NK T cell (Assay: 10x 3' v3, Tissue: blood)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","plasma cell (Assay: 10x 3' v3, Tissue: blood)","hematopoietic stem cell (Assay: 10x 3' v3, Tissue: blood)","B cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","effector CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","T cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","type I NK T cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","effector CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","innate lymphoid cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","plasma cell (Assay: 10x 3' v3, Tissue: inguinal lymph node)","effector CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lymph node)","type I NK T cell (Assay: 10x 3' v3, Tissue: lymph node)","effector CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lymph node)","innate lymphoid cell (Assay: 10x 3' v3, Tissue: lymph node)","macrophage (Assay: 10x 3' v3, Tissue: lymph node)","regulatory T cell (Assay: 10x 3' v3, Tissue: lymph node)","T cell (Assay: 10x 3' v3, Tissue: lymph node)","plasma cell (Assay: 10x 3' v3, Tissue: lymph node)","mature NK T cell (Assay: 10x 3' v3, Tissue: lymph node)","mast cell (Assay: 10x 3' v3, Tissue: lymph node)","CD141-positive myeloid dendritic cell (Assay: 10x 3' v3, Tissue: lymph node)","intermediate monocyte (Assay: 10x 3' v3, Tissue: lymph node)","stromal cell (Assay: 10x 3' v3, Tissue: lymph node)","CD1c-positive myeloid dendritic cell (Assay: 10x 3' v3, Tissue: lymph node)","classical monocyte (Assay: 10x 3' v3, Tissue: lymph node)","endothelial cell (Assay: 10x 3' v3, Tissue: lymph node)","naive B cell (Assay: 10x 3' v3, Tissue: parotid gland)","memory B cell (Assay: 10x 3' v3, Tissue: parotid gland)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: parotid gland)","mature NK T cell (Assay: 10x 3' v3, Tissue: parotid gland)","fibroblast (Assay: 10x 3' v3, Tissue: parotid gland)","endothelial cell of lymphatic vessel (Assay: 10x 3' v3, Tissue: parotid gland)","adventitial cell (Assay: 10x 3' v3, Tissue: parotid gland)","B cell (Assay: 10x 3' v3, Tissue: parotid gland)","endothelial cell (Assay: 10x 3' v3, Tissue: parotid gland)","monocyte (Assay: 10x 3' v3, Tissue: parotid gland)","duct epithelial cell (Assay: 10x 3' v3, Tissue: parotid gland)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: parotid gland)","neutrophil (Assay: 10x 3' v3, Tissue: parotid gland)","macrophage (Assay: 10x 3' v3, Tissue: spleen)","intermediate monocyte (Assay: 10x 3' v3, Tissue: spleen)","endothelial cell (Assay: 10x 3' v3, Tissue: spleen)","neutrophil (Assay: 10x 3' v3, Tissue: spleen)","CD4-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: spleen)","type I NK T cell (Assay: 10x 3' v3, Tissue: spleen)","mature NK T cell (Assay: 10x 3' v3, Tissue: spleen)","innate lymphoid cell (Assay: 10x 3' v3, Tissue: spleen)","erythrocyte (Assay: 10x 3' v3, Tissue: spleen)","hematopoietic stem cell (Assay: 10x 3' v3, Tissue: spleen)","epithelial cell (Assay: 10x 3' v3, Tissue: anterior part of tongue)","leukocyte (Assay: 10x 3' v3, Tissue: posterior part of tongue)","fibroblast (Assay: 10x 3' v3, Tissue: posterior part of tongue)","vein endothelial cell (Assay: 10x 3' v3, Tissue: posterior part of tongue)","pericyte (Assay: 10x 3' v3, Tissue: posterior part of tongue)","keratinocyte (Assay: 10x 3' v3, Tissue: posterior part of tongue)","fibroblast of breast (Assay: 10x 3' v3, Tissue: mammary gland)","T cell (Assay: 10x 3' v3, Tissue: mammary gland)","macrophage (Assay: 10x 3' v3, Tissue: mammary gland)","pericyte (Assay: 10x 3' v3, Tissue: mammary gland)","vascular associated smooth muscle cell (Assay: 10x 3' v3, Tissue: mammary gland)","vein endothelial cell (Assay: 10x 3' v3, Tissue: mammary gland)","basal cell (Assay: 10x 3' v3, Tissue: mammary gland)","plasma cell (Assay: 10x 3' v3, Tissue: mammary gland)","endothelial cell of artery (Assay: 10x 3' v3, Tissue: mammary gland)","T cell (Assay: 10x 3' v3, Tissue: endometrium)","macrophage (Assay: 10x 3' v3, Tissue: endometrium)","epithelial cell of uterus (Assay: 10x 3' v3, Tissue: endometrium)","endothelial cell (Assay: 10x 3' v3, Tissue: endometrium)","epithelial cell (Assay: 10x 3' v3, Tissue: endometrium)","endothelial cell of lymphatic vessel (Assay: 10x 3' v3, Tissue: endometrium)","vascular associated smooth muscle cell (Assay: 10x 3' v3, Tissue: myometrium)","myometrial cell (Assay: 10x 3' v3, Tissue: myometrium)","endothelial cell (Assay: 10x 3' v3, Tissue: myometrium)","fibroblast (Assay: 10x 3' v3, Tissue: myometrium)","pericyte (Assay: 10x 3' v3, Tissue: myometrium)","conjunctival epithelial cell (Assay: 10x 3' v3, Tissue: eye)","microglial cell (Assay: 10x 3' v3, Tissue: eye)","eye photoreceptor cell (Assay: 10x 3' v3, Tissue: eye)","Mueller cell (Assay: 10x 3' v3, Tissue: eye)","T cell (Assay: 10x 3' v3, Tissue: eye)","epithelial cell of lacrimal sac (Assay: 10x 3' v3, Tissue: eye)","keratocyte (Assay: 10x 3' v3, Tissue: eye)","conjunctival epithelial cell (Assay: 10x 3' v3, Tissue: conjunctiva)","endothelial cell (Assay: 10x 3' v3, Tissue: adipose tissue)","T cell (Assay: 10x 3' v3, Tissue: adipose tissue)","macrophage (Assay: 10x 3' v3, Tissue: adipose tissue)","myofibroblast cell (Assay: 10x 3' v3, Tissue: adipose tissue)","mesenchymal stem cell (Assay: 10x 3' v3, Tissue: adipose tissue)","neutrophil (Assay: 10x 3' v3, Tissue: adipose tissue)","mature NK T cell (Assay: 10x 3' v3, Tissue: subcutaneous adipose tissue)","myofibroblast cell (Assay: 10x 3' v3, Tissue: subcutaneous adipose tissue)","macrophage (Assay: 10x 3' v3, Tissue: subcutaneous adipose tissue)","endothelial cell (Assay: 10x 3' v3, Tissue: subcutaneous adipose tissue)","T cell (Assay: 10x 3' v3, Tissue: subcutaneous adipose tissue)","macrophage (Assay: 10x 3' v3, Tissue: skin of body)","stromal cell (Assay: 10x 3' v3, Tissue: skin of body)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: skin of body)","mature NK T cell (Assay: 10x 3' v3, Tissue: skin of body)","mast cell (Assay: 10x 3' v3, Tissue: skin of body)","muscle cell (Assay: 10x 3' v3, Tissue: skin of body)","CD8-positive, alpha-beta cytotoxic T cell (Assay: 10x 3' v3, Tissue: skin of body)","CD1c-positive myeloid dendritic cell (Assay: 10x 3' v3, Tissue: skin of body)","endothelial cell (Assay: 10x 3' v3, Tissue: skin of body)","CD4-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: skin of body)","naive thymus-derived CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: skin of body)","epithelial cell (Assay: 10x 3' v3, Tissue: skin of body)","monocyte (Assay: 10x 3' v3, Tissue: bone marrow)","hematopoietic stem cell (Assay: 10x 3' v3, Tissue: bone marrow)","erythroid progenitor cell (Assay: 10x 3' v3, Tissue: bone marrow)","mature NK T cell (Assay: 10x 3' v3, Tissue: bone marrow)","granulocyte (Assay: 10x 3' v3, Tissue: bone marrow)","macrophage (Assay: 10x 3' v3, Tissue: bone marrow)","common myeloid progenitor (Assay: 10x 3' v3, Tissue: bone marrow)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: bone marrow)","neutrophil (Assay: 10x 3' v3, Tissue: bone marrow)","cardiac endothelial cell (Assay: 10x 3' v3, Tissue: cardiac atrium)","hepatocyte (Assay: 10x 3' v3, Tissue: cardiac atrium)","cardiac muscle cell (Assay: 10x 3' v3, Tissue: cardiac ventricle)","cardiac endothelial cell (Assay: 10x 3' v3, Tissue: cardiac ventricle)","hepatocyte (Assay: 10x 3' v3, Tissue: cardiac ventricle)","fibroblast of cardiac tissue (Assay: 10x 3' v3, Tissue: cardiac ventricle)","pancreatic acinar cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","T cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","endothelial cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","myeloid cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","pancreatic stellate cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","pancreatic ductal cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","plasma cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","type B pancreatic cell (Assay: 10x 3' v3, Tissue: exocrine pancreas)","epithelial cell (Assay: 10x 3' v3, Tissue: prostate gland)","fibroblast (Assay: 10x 3' v3, Tissue: prostate gland)","club cell (Assay: 10x 3' v3, Tissue: prostate gland)","mature NK T cell (Assay: 10x 3' v3, Tissue: prostate gland)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: prostate gland)","endothelial cell (Assay: 10x 3' v3, Tissue: prostate gland)","smooth muscle cell (Assay: 10x 3' v3, Tissue: prostate gland)","fibroblast (Assay: Smart-seq2, Tissue: subcutaneous adipose tissue)","endothelial cell (Assay: Smart-seq2, Tissue: skin of abdomen)","mast cell (Assay: Smart-seq2, Tissue: skin of abdomen)","endothelial cell (Assay: Smart-seq2, Tissue: skin of chest)","CD4-positive, alpha-beta T cell (Assay: Smart-seq2, Tissue: bone marrow)","plasma cell (Assay: Smart-seq2, Tissue: bone marrow)","erythroid progenitor cell (Assay: Smart-seq2, Tissue: bone marrow)","epithelial cell of uterus (Assay: Smart-seq2, Tissue: uterus)","luminal epithelial cell of mammary gland (Assay: Smart-seq2, Tissue: mammary gland)","endothelial cell of vascular tree (Assay: Smart-seq2, Tissue: muscle of pelvic diaphragm)","ciliated cell (Assay: Smart-seq2, Tissue: trachea)","basal cell (Assay: Smart-seq2, Tissue: trachea)","fibroblast (Assay: Smart-seq2, Tissue: trachea)","memory B cell (Assay: Smart-seq2, Tissue: spleen)","plasma cell (Assay: Smart-seq2, Tissue: spleen)","mature NK T cell (Assay: Smart-seq2, Tissue: spleen)","plasma cell (Assay: Smart-seq2, Tissue: lymph node)","adventitial cell (Assay: Smart-seq2, Tissue: parotid gland)","basal cell (Assay: Smart-seq2, Tissue: posterior part of tongue)","epithelial cell (Assay: Smart-seq2, Tissue: prostate gland)","erythrocyte (Assay: 10x 3' v3, Tissue: bone marrow)","endothelial cell (Assay: 10x 3' v3, Tissue: liver)","erythrocyte (Assay: 10x 3' v3, Tissue: liver)","macrophage (Assay: 10x 3' v3, Tissue: parotid gland)","basal cell (Assay: 10x 3' v3, Tissue: submandibular gland)","plasma cell (Assay: 10x 3' v3, Tissue: submandibular gland)","macrophage (Assay: 10x 3' v3, Tissue: submandibular gland)","ionocyte (Assay: 10x 3' v3, Tissue: submandibular gland)","duct epithelial cell (Assay: 10x 3' v3, Tissue: submandibular gland)","endothelial cell of lymphatic vessel (Assay: 10x 3' v3, Tissue: submandibular gland)","endothelial cell (Assay: 10x 3' v3, Tissue: submandibular gland)","fibroblast (Assay: 10x 3' v3, Tissue: submandibular gland)","naive regulatory T cell (Assay: 10x 3' v3, Tissue: thymus)","T follicular helper cell (Assay: 10x 3' v3, Tissue: thymus)","CD8-positive, alpha-beta cytotoxic T cell (Assay: 10x 3' v3, Tissue: thymus)","B cell (Assay: 10x 3' v3, Tissue: thymus)","medullary thymic epithelial cell (Assay: 10x 3' v3, Tissue: thymus)","macrophage (Assay: 10x 3' v3, Tissue: thymus)","vascular associated smooth muscle cell (Assay: 10x 3' v3, Tissue: thymus)","plasma cell (Assay: 10x 3' v3, Tissue: thymus)","vein endothelial cell (Assay: 10x 3' v3, Tissue: thymus)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: thymus)","endothelial cell of artery (Assay: 10x 3' v3, Tissue: thymus)","mature NK T cell (Assay: 10x 3' v3, Tissue: thymus)","monocyte (Assay: 10x 3' v3, Tissue: thymus)","endothelial cell of lymphatic vessel (Assay: 10x 3' v3, Tissue: thymus)","corneal epithelial cell (Assay: 10x 3' v3, Tissue: cornea)","conjunctival epithelial cell (Assay: 10x 3' v3, Tissue: cornea)","radial glial cell (Assay: 10x 3' v3, Tissue: cornea)","stem cell (Assay: 10x 3' v3, Tissue: cornea)","keratocyte (Assay: 10x 3' v3, Tissue: cornea)","fibroblast (Assay: 10x 3' v3, Tissue: cornea)","retinal blood vessel endothelial cell (Assay: 10x 3' v3, Tissue: cornea)","melanocyte (Assay: 10x 3' v3, Tissue: cornea)","eye photoreceptor cell (Assay: 10x 3' v3, Tissue: retinal neural layer)","Mueller cell (Assay: 10x 3' v3, Tissue: retinal neural layer)","retinal blood vessel endothelial cell (Assay: 10x 3' v3, Tissue: sclera)","keratocyte (Assay: 10x 3' v3, Tissue: sclera)","stromal cell (Assay: 10x 3' v3, Tissue: sclera)","endothelial cell (Assay: 10x 3' v3, Tissue: sclera)","macrophage (Assay: 10x 3' v3, Tissue: sclera)","conjunctival epithelial cell (Assay: 10x 3' v3, Tissue: sclera)","T cell (Assay: 10x 3' v3, Tissue: bladder organ)","macrophage (Assay: 10x 3' v3, Tissue: bladder organ)","myofibroblast cell (Assay: 10x 3' v3, Tissue: bladder organ)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: bladder organ)","smooth muscle cell (Assay: 10x 3' v3, Tissue: bladder organ)","pericyte (Assay: 10x 3' v3, Tissue: bladder organ)","mast cell (Assay: 10x 3' v3, Tissue: bladder organ)","mature NK T cell (Assay: 10x 3' v3, Tissue: bladder organ)","endothelial cell of lymphatic vessel (Assay: 10x 3' v3, Tissue: bladder organ)","vein endothelial cell (Assay: 10x 3' v3, Tissue: bladder organ)","B cell (Assay: 10x 3' v3, Tissue: bladder organ)","CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: large intestine)","enterocyte of epithelium of large intestine (Assay: 10x 3' v3, Tissue: large intestine)","monocyte (Assay: 10x 3' v3, Tissue: large intestine)","plasma cell (Assay: 10x 3' v3, Tissue: large intestine)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: large intestine)","fibroblast (Assay: 10x 3' v3, Tissue: large intestine)","large intestine goblet cell (Assay: 10x 3' v3, Tissue: large intestine)","paneth cell of colon (Assay: 10x 3' v3, Tissue: large intestine)","B cell (Assay: 10x 3' v3, Tissue: large intestine)","transit amplifying cell of colon (Assay: 10x 3' v3, Tissue: large intestine)","intestinal enteroendocrine cell (Assay: 10x 3' v3, Tissue: large intestine)","respiratory goblet cell (Assay: 10x 3' v3, Tissue: lung)","T cell (Assay: 10x 3' v3, Tissue: prostate gland)","myeloid cell (Assay: 10x 3' v3, Tissue: prostate gland)","CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: small intestine)","enterocyte of epithelium of small intestine (Assay: 10x 3' v3, Tissue: small intestine)","neutrophil (Assay: 10x 3' v3, Tissue: small intestine)","transit amplifying cell of small intestine (Assay: 10x 3' v3, Tissue: small intestine)","small intestine goblet cell (Assay: 10x 3' v3, Tissue: small intestine)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: small intestine)","B cell (Assay: 10x 3' v3, Tissue: small intestine)","monocyte (Assay: 10x 3' v3, Tissue: small intestine)","paneth cell of epithelium of small intestine (Assay: 10x 3' v3, Tissue: small intestine)","plasma cell (Assay: 10x 3' v3, Tissue: small intestine)","mast cell (Assay: 10x 3' v3, Tissue: small intestine)","intestinal enteroendocrine cell (Assay: 10x 3' v3, Tissue: small intestine)","intestinal crypt stem cell of small intestine (Assay: 10x 3' v3, Tissue: small intestine)","mature NK T cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","stromal cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","endothelial cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","mast cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","macrophage (Assay: 10x 3' v3, Tissue: skin of abdomen)","muscle cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","T cell (Assay: 10x 3' v3, Tissue: skin of abdomen)","endothelial cell (Assay: 10x 3' v3, Tissue: skin of chest)","stromal cell (Assay: 10x 3' v3, Tissue: skin of chest)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: skin of chest)","muscle cell (Assay: 10x 3' v3, Tissue: skin of chest)","mature NK T cell (Assay: 10x 3' v3, Tissue: skin of chest)","DN3 thymocyte (Assay: 10x 3' v3, Tissue: thymus)","DN1 thymic pro-T cell (Assay: 10x 3' v3, Tissue: thymus)","innate lymphoid cell (Assay: 10x 3' v3, Tissue: thymus)","basal cell (Assay: 10x 3' v3, Tissue: anterior part of tongue)","keratinocyte (Assay: 10x 3' v3, Tissue: anterior part of tongue)","leukocyte (Assay: 10x 3' v3, Tissue: anterior part of tongue)","mesenchymal stem cell (Assay: 10x 3' v3, Tissue: muscle of abdomen)","skeletal muscle satellite stem cell (Assay: 10x 3' v3, Tissue: muscle of abdomen)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: muscle of abdomen)","pericyte (Assay: 10x 3' v3, Tissue: muscle of abdomen)","macrophage (Assay: 10x 3' v3, Tissue: muscle of abdomen)","endothelial cell of vascular tree (Assay: 10x 3' v3, Tissue: muscle of abdomen)","mesenchymal stem cell (Assay: 10x 3' v3, Tissue: muscle of pelvic diaphragm)","macrophage (Assay: 10x 3' v3, Tissue: muscle of pelvic diaphragm)","skeletal muscle satellite stem cell (Assay: 10x 3' v3, Tissue: muscle of pelvic diaphragm)","endothelial cell of vascular tree (Assay: 10x 3' v3, Tissue: muscle of pelvic diaphragm)","T cell (Assay: 10x 3' v3, Tissue: muscle of pelvic diaphragm)","smooth muscle cell (Assay: 10x 3' v3, Tissue: vasculature)","macrophage (Assay: 10x 3' v3, Tissue: vasculature)","pericyte (Assay: 10x 3' v3, Tissue: vasculature)","smooth muscle cell (Assay: 10x 3' v3, Tissue: coronary artery)","T cell (Assay: 10x 3' v3, Tissue: coronary artery)","macrophage (Assay: 10x 3' v3, Tissue: coronary artery)","endothelial cell of artery (Assay: 10x 3' v3, Tissue: coronary artery)","pericyte (Assay: 10x 3' v3, Tissue: coronary artery)","plasma cell (Assay: 10x 3' v3, Tissue: bladder organ)","bladder urothelial cell (Assay: Smart-seq2, Tissue: bladder organ)","CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: blood)","monocyte (Assay: 10x 3' v3, Tissue: blood)","macrophage (Assay: 10x 3' v3, Tissue: blood)","kidney epithelial cell (Assay: 10x 3' v3, Tissue: kidney)","B cell (Assay: 10x 3' v3, Tissue: kidney)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: kidney)","macrophage (Assay: 10x 3' v3, Tissue: kidney)","CD4-positive helper T cell (Assay: 10x 3' v3, Tissue: kidney)","kidney epithelial cell (Assay: Smart-seq2, Tissue: kidney)","enterocyte (Assay: 10x 3' v3, Tissue: large intestine)","intestinal crypt stem cell (Assay: 10x 3' v3, Tissue: large intestine)","goblet cell (Assay: 10x 3' v3, Tissue: large intestine)","basophil (Assay: 10x 3' v3, Tissue: lung)","lung ciliated cell (Assay: 10x 3' v3, Tissue: lung)","dendritic cell (Assay: 10x 3' v3, Tissue: lung)","CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lung)","basal cell (Assay: 10x 3' v3, Tissue: lung)","plasma cell (Assay: 10x 3' v3, Tissue: lung)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lung)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: lung)","type I pneumocyte (Assay: 10x 3' v3, Tissue: lung)","vein endothelial cell (Assay: 10x 3' v3, Tissue: lung)","fibroblast (Assay: 10x 3' v3, Tissue: lung)","club cell (Assay: 10x 3' v3, Tissue: lung)","lung microvascular endothelial cell (Assay: 10x 3' v3, Tissue: lung)","type II pneumocyte (Assay: Smart-seq2, Tissue: lung)","macrophage (Assay: Smart-seq2, Tissue: lung)","basal cell (Assay: Smart-seq2, Tissue: lung)","adventitial cell (Assay: Smart-seq2, Tissue: lung)","intermediate monocyte (Assay: 10x 3' v3, Tissue: lung)","naive B cell (Assay: 10x 3' v3, Tissue: lymph node)","memory B cell (Assay: 10x 3' v3, Tissue: lymph node)","naive thymus-derived CD4-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: lymph node)","CD4-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: lymph node)","CD8-positive, alpha-beta memory T cell (Assay: 10x 3' v3, Tissue: lymph node)","memory B cell (Assay: Smart-seq2, Tissue: lymph node)","memory B cell (Assay: Smart-seq2, Tissue: inguinal lymph node)","skeletal muscle satellite stem cell (Assay: 10x 3' v3, Tissue: muscle tissue)","pericyte (Assay: 10x 3' v3, Tissue: muscle tissue)","endothelial cell of vascular tree (Assay: 10x 3' v3, Tissue: muscle tissue)","macrophage (Assay: 10x 3' v3, Tissue: muscle tissue)","mesenchymal stem cell (Assay: 10x 3' v3, Tissue: muscle tissue)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: muscle tissue)","fast muscle cell (Assay: 10x 3' v3, Tissue: muscle tissue)","slow muscle cell (Assay: 10x 3' v3, Tissue: muscle tissue)","endothelial cell of vascular tree (Assay: Smart-seq2, Tissue: muscle tissue)","macrophage (Assay: Smart-seq2, Tissue: muscle tissue)","mesenchymal stem cell (Assay: Smart-seq2, Tissue: muscle tissue)","pericyte (Assay: 10x 3' v3, Tissue: rectus abdominis muscle)","skeletal muscle satellite stem cell (Assay: 10x 3' v3, Tissue: rectus abdominis muscle)","capillary endothelial cell (Assay: 10x 3' v3, Tissue: rectus abdominis muscle)","endothelial cell of vascular tree (Assay: 10x 3' v3, Tissue: rectus abdominis muscle)","macrophage (Assay: 10x 3' v3, Tissue: rectus abdominis muscle)","endothelial cell (Assay: 10x 3' v3, Tissue: endocrine pancreas)","pancreatic acinar cell (Assay: 10x 3' v3, Tissue: endocrine pancreas)","pancreatic ductal cell (Assay: 10x 3' v3, Tissue: endocrine pancreas)","intestinal crypt stem cell (Assay: 10x 3' v3, Tissue: small intestine)","enterocyte (Assay: 10x 3' v3, Tissue: small intestine)","CD8-positive, alpha-beta T cell (Assay: 10x 3' v3, Tissue: thymus)","memory B cell (Assay: 10x 3' v3, Tissue: thymus)","naive B cell (Assay: 10x 3' v3, Tissue: thymus)","fast muscle cell (Assay: 10x 3' v3, Tissue: thymus)","thymocyte (Assay: 10x 3' v3, Tissue: thymus)","fibroblast (Assay: Smart-seq2, Tissue: thymus)","connective tissue cell (Assay: 10x 3' v3, Tissue: trachea)","fibroblast (Assay: 10x 3' v3, Tissue: aorta)","macrophage (Assay: 10x 3' v3, Tissue: aorta)","smooth muscle cell (Assay: 10x 3' v3, Tissue: aorta)","endothelial cell (Assay: 10x 3' v3, Tissue: aorta)","mature NK T cell (Assay: 10x 3' v3, Tissue: aorta)","pericyte (Assay: 10x 3' v3, Tissue: aorta)","mast cell (Assay: 10x 3' v3, Tissue: aorta)","pancreatic A cell (Assay: 10x 3' v2, Tissue: islet of Langerhans)","pancreatic D cell (Assay: 10x 3' v2, Tissue: islet of Langerhans)","type B pancreatic cell (Assay: 10x 3' v2, Tissue: islet of Langerhans)"]))
        
        with st.expander("Advanced Options", expanded=False):
            col1, col2 = st.columns([3, 3])
            
            with col1:
                ct_freq_slider = st.slider("Cell Type Frequency", 0.0, 1.0, 0.25, step = 0.05, help="Frequency of the cell type of interest.")
                sample_size_ratio_slider = st.slider("Sample Size Ratio", 0.0, 50.0, 1.0, step = 0.05, help="ratio between sample size of group 0 (control group) and group 1 (Ratio=1 in case of balanced design)")
                ref_study = st.selectbox("Reference Study", ["Blueprint (CLL) iCLL-mCLL", "Blueprint (CLL) mCLL-uCLL", "Blueprint (CLL) uCLL-iCLL", "Moreno-Moral (Macrophages)", "Nicodemus-Johnson_AEC", "Pancreas_alphabeta", "Pancreas_ductacinar", "Custom"])
                total_budget = st.slider("Total Budget", step=500,min_value =0,value = 50000, help="The total budget available for the sequencing")
            
            with col2:
                parameter_grid = st.selectbox("Parameter Grid", ["samples - cells per sample", "samples - reads per cell", "cells per sample - reads per cell"])
                cells_min = st.slider("Cells (min)", value=10, step=1, help="Minimal value of the tested ranges for the parameter on the x-Axis.")
                cells_max = st.slider("Cells (max)", value=50, step=1, help="Maximum value of the tested ranges for the parameter on the x-Axis.")
                steps = st.slider("Steps", min_value=0, value=5, step=1, help= "number of values in the parameter ranges for the parameter grid")

        with st.expander("Cost and Experimental Parameters", expanded=False):
            col1, col2 = st.columns([3, 3])
            with col1:
                cost_10x_kit = st.slider("Cost 10X kit", value = 5600, step=100,min_value=0, help="Cost for one 10X Genomics kit")     
                cost_flow_cell = st.slider("Cost Flow Cell", value = 14032, step=100,min_value=0, help="Cost for one flow cell")
                reads_per_flow_cell = st.slider("Number of reads per flow cell", value = 4100*10^6, step=10000,min_value=0)   
                cells_per_lane = st.slider("Cells per lane", value = 8000, step=500,min_value=0, help="Number of cells meassured on one 10X lane (dependent on the parameter \"Reactions Per Kit\")")
                
            with col2: 
                reactions_per_kit = st.slider("Reactions Per Kit", value = 6, step = 1, min_value= 1, help="Number of reactions/lanes on one 10X kit (different kit versions possible)")
                p_value = st.slider("P-value", value=0.05,step=0.01,min_value=0.0,max_value=1.0, help="Significance threshold")
                multiple_testing_method = st.selectbox("Multiple testing method", ["FDR", "FWER", "None"])
        
        with st.expander("Mapping and Multiplet estimation", expanded=False):
            col1, col2 = st.columns([3, 3])
            with col1:
                mapping_efficiency = st.slider("Mapping efficiency", value = 0.8,step=0.05,min_value=0.0,max_value=1.0)
                multiplet_rate = st.slider("Multiplet Rate", value = 7.67e-06,step=1e-6,min_value=0.0, help="Rate factor to calculate the number of multiplets dependent on the number of cells loaded per lane. We assume a linear relationship of multiplet fraction = cells per lane * multiplet rate.")
                multiplet_factor = st.slider("Multiplet Factor", value = 1.82, step=0.1,min_value=1.0, help="Multiplets have a higher fraction of reads per cell than singlets, the multiplet factor shows the ratio between the reads.")
            
            with col2:
                min_num_UMI_per_gene = st.slider("Minimal number of UMI per gene", value = 3, step=1,min_value=1)
                fraction_of_indiv = st.slider("Fraction of individuals", value = 0.5,step=0.05,min_value=0.0,max_value=1.0)
                skip_power = st.checkbox("Skip power for lowly expressed genes")
                use_simulated = st.checkbox("Use simulated power for eQTLs")

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
    else:
        st.warning("No data available for plotting. Please fetch or upload data first.")

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