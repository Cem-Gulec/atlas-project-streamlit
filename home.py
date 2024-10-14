import streamlit as st

def show_home_page():
    st.markdown("""
    <style>
    .main-title {
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .description {
        font-size: 16px;
        line-height: 1.5;
        margin-bottom: 20px;
    }
    .highlight {
        color: #FF4B4B;
        font-weight: bold;
    }
    .button-container {
        display: flex;
        justify-content: space-between;
        margin-top: 30px;
    }
    .custom-button {
        background-color: #0E1117;
        border: 2px solid white;
        color: #31333F;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 5px;
    }
    /* Custom CSS for Streamlit button */
    .stButton > button {
        background-color: #0E1117;
        border: 2px solid white;
        color: #259bc4;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 5px;
        width: auto;
        height: auto;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-title">Welcome to scPower</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="description">
    <span class="highlight">scPower</span> is a R package for design and power analysis of cell type specific 
                interindividual DE and eQTL studies using single cell RNA-seq. It enables the user to calculate 
                the power for a given experimental setup and to choose for a restricted budget the optimal combination 
                of experimental parameters which maximizes the power. Necessary experimental priors, e.g. effect sizes 
                and expression distributions, can be taken from example data sets, saved in the package, or estimated from new data sets. 
                The tool was evaluated with data from different tissues and single cell technologies, based on UMI counts and read counts.
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4  = st.columns([7, 9, 6, 7])

    with col1:
        if st.button("📘 Learn More"):
            st.session_state.page = "Description"
            st.rerun()

    with col2:
        if st.button("🧬 Detect DE/eQTL genes"):
            st.session_state.page = "Detect DE/eQTL Genes"
            st.rerun()

    with col3:
        st.markdown("""
        <a href="https://github.com/heiniglab/scPower" target="_blank" class="custom-button">Github Page</a>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <a href="https://scpower-cell-atlas.readthedocs.io/en/latest/" target="_blank" class="custom-button">Documentation</a>
        """, unsafe_allow_html=True)