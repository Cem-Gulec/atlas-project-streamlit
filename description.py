import streamlit as st

def show_description_page():
    st.title("Welcome to scPower")
    st.subheader("A statistical framework for design and power analysis of multi-sample single cell transcriptomics experiments")

    st.write("The tool supports the user to set the experimental parameters of cell type specific inter-individual DE and eQTL analysis using single cell RNA-seq data.")

    st.image("description_figure.png", use_column_width=True)

    st.write("Experimental design suggestions are made in a way to optimize the power of the experiment.")

    st.subheader("scPower offers optimization for two different experimental settings:")
    col1, col2 = st.columns(2)
    with col1:
        st.write("- **Detect cell types** (referred to as \"cell type detection probability\" in the figure above)")
    with col2:
        st.write("- **Detect DE/eQTL genes** (referred to as \"Overall detection power\")")

    st.info("This website is specifically designed for 10X Genomics experiments. We refer users of other single cell RNA-seq technologies, such as Drop-seq and Smart-seq, to the [R package](https://github.com/heiniglab/scPower), which allows higher level of customization and is also suitable for those platforms.")

    st.header("Detect DE/eQTL genes")
    st.write("""
    In this section you can find the parameter combination which maximizes the detection power of DE / eQTL genes. The **main plot** on the right side shows the **detection power** depending on parameter combinations. You can choose 2 out of the 3 cost determining factors (sample size, cells per person, read depth) to be displayed on x- and y-Axis. Due to the fixed budget, the third one can be determined and will be displayed as circle size.

    Depending on the overall budget, not all parameter combinations will be possible and some spots will stay white in the grid. An arrow called "selected study" points on the study with the highest detection power and the two plots below visualize the power curves for this study. The arrow can be set to any parameter combination by clicking on the main plot.

    The detection power is the product of the **expression probability** and the **DE/eQTL power**. The expression probability shows how likely it is that the DE/eQTL genes are expressed, while the DE/eQTL power shows how likely it is to detect the genes as significant, given that they are expressed. The **two lower plots** show the influence of the parameters on each of the probabilities.
    """)

    st.subheader("Parameters")
    st.write("The power analysis can be tailored to the users experimental setup with a lot of different parameters. In case some parameters are unknown, the user can fall back to the defaults we provide.")

    parameters = {
        "General parameters": "",
        "Multiple testing correction": "Both the p-value and the multiple testing strategy can be chosen. We recommend using FWER adjustement for eQTL studies and FDR adjustment for DE studies.",
        "Mapping and multiplet estimation": "The more cells are loaded on a lane, the more multiplets are produced. These need to be discared before the analysis. Furthermore, since multiplets have a higher fraction of reads per cell than singlets, higher multiplet rates also reduce the target read depth.",
        "Expression cutoffs": "A gene is defined as expressed, if it has a certain fraction of UMI counts per gene in a certain fraction of individuals (both parameters can be set). This influences the expression probability.",
        "Special parameters": "The method of power calculation can be changed to speed up calculation or to increase accuracy (especially important for eQTL calculation)."
    }

    for category, description in parameters.items():
        st.markdown(f"**{category}**")
        if description:
            st.write(description)

    st.header("Detect cell types")
    st.write("""
    This section determines the power to detect a sufficient number of cells from a cell type of interest in each individual. This is important as a cell-type specific DE or eQTL analysis is only possible if enough cells of this cell type are detected. The method calculates the minimal number of cells per individual which are necessary to reach a sufficient power threshold.
    """)

    st.header("References")
    st.write("""
    A detailed description of the complete model can be found in our publication:
    [Schmid, K. T. et al. scPower accelerates and optimizes the design of multi-sample single cell transcriptomic studies. Nature Communications (2021)](https://doi.org/10.1038/s41467-021-26779-7)

    All code including an offline version of this website, build with R shiny, is available as an R package on [Github](https://github.com/heiniglab/scPower).

    With the R package, the user can also fit and incorporate own priors for expression probabilities and effect sizes. This is due to runtime reasons not possible over the webserver.

    The package contains a detailed introduction vignette explaining all necessary steps for the inclusion of custom priors.
    """)