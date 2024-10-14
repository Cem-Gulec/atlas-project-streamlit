import streamlit as st

def show_tutorial_page():
    st.title("Tutorial: How to Use the scPower Cell Atlas")

    st.markdown("""
    Welcome to the scPower Cell Atlas tutorial! This guide will walk you through the main features of our application and how to use them effectively.

    ## 1. Navigation """)

    st.image("images/navigation.png")
    
    st.markdown("""
    Use the sidebar on the left to navigate between different pages:
    - **Home**: Overview of the scPower Cell Atlas
    - **Description**: Detailed information about the tool
    - **Detect DE/eQTL Genes**: Main analysis page
    - **Tutorial**: This guide
    - **License Statement**: Legal information

    ## 2. Detect DE/eQTL Genes Page

    This is the main analysis page. Here's how to use it:

    ### 2.1 General Parameters
    - Choose the study type (DE or eQTL)
    - Select the organism
    - Choose the assay, tissue, and cell type of interest

    ### 2.2 Advanced Options
    - Set cell type frequency and sample size ratio
    - Choose a reference study or select "Custom"
    - Set the total budget for sequencing
    - Select the parameter grid and adjust the ranges

    ### 2.3 Cost and Experimental Parameters
    - Adjust costs for 10X kit and flow cell
    - Set experimental parameters like p-value and multiple testing method

    ### 2.4 Mapping and Multiplet Estimation
    - Set mapping efficiency and multiplet rate
    - Adjust other technical parameters

    ### 2.5 Running the Analysis
    - After setting all parameters, click "Run analysis"
    - The tool will generate scatter and influence plots

    ## 3. Interpreting Results

    ### 3.1 Scatter Plot
    - Shows detection power based on cells per individual, read depth, and sample size
    - Use dropdowns to select X-axis, Y-axis, and Size-axis variables

    ### 3.2 Influence Plot
    - Demonstrates how different parameters influence detection power
    - Dashed lines indicate the selected study's parameters

    ## 4. Tips for Effective Use

    - Experiment with different parameter combinations to optimize your study design
    - Pay attention to the trade-offs between sample size, cells per sample, and read depth
    - Use the influence plot to understand which parameters have the most impact on your study's power

    Remember, the goal is to find the optimal balance between cost and detection power for your specific research question.

    If you have any questions or need further assistance, please don't hesitate to contact our support team.
    """)