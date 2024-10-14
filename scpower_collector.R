#!/usr/bin/env Rscript

# Load required libraries
library(jsonlite)
library(scPower)  # Assuming the optimize.constant.budget.restrictedDoublets function is in this package

load("disp.fun.param.RData")
load("gamma.mixed.fits.RData")
load("read.umi.fit.RData")
load("ref.study.RData")

# Read command-line arguments
args <- commandArgs(trailingOnly = TRUE)

if (length(args) == 0) {
  stop("No arguments provided. Please provide a path to the JSON file.")
}

# Read and parse JSON input
tryCatch({
  params <- fromJSON(args[1])
}, error = function(e) {
  cat("Error parsing JSON file: ", conditionMessage(e), "\n")
  cat("File path: ", args[1], "\n")
  quit(status = 1)
})

# Extract parameters from the JSON object
totalBudget <- params$totalBudget
type <- params$type
ct <- params$ct
ct.freq <- params$ct.freq
costKit <- params$costKit
costFlowCell <- params$costFlowCell
readsPerFlowcell <- params$readsPerFlowcell
ref.study.name <- params$ref.study.name
cellsPerLane <- params$cellsPerLane
nSamplesRange <- params$nSamplesRange
nCellsRange <- params$nCellsRange
readDepthRange <- params$readDepthRange
mappingEfficiency <- params$mappingEfficiency
multipletRate <- params$multipletRate
multipletFactor <- params$multipletFactor
min.UMI.counts <- params$min.UMI.counts
perc.indiv.expr <- params$perc.indiv.expr
sign.threshold <- params$sign.threshold
MTmethod <- params$MTmethod
useSimulatedPower <- params$useSimulatedPower
speedPowerCalc <- params$speedPowerCalc
indepSNPs <- params$indepSNPs
ssize.ratio.de <- params$ssize.ratio.de
reactionsPerKit <- params$reactionsPerKit

# Call the optimize.constant.budget.restrictedDoublets function
tryCatch({
  power.study.plot <- optimize.constant.budget.restrictedDoublets(
    totalBudget = totalBudget,
    type = type,
    ct = ct,
    ct.freq = ct.freq,
    costKit = costKit,
    costFlowCell = costFlowCell,
    readsPerFlowcell = readsPerFlowcell,
    ref.study,
    ref.study.name = ref.study.name,
    cellsPerLane = cellsPerLane,
    read.umi.fit[read.umi.fit$type=="10X_PBMC_1",],
    gamma.mixed.fits,
    disp.fun.param,
    nSamplesRange = nSamplesRange,
    nCellsRange = nCellsRange,
    readDepthRange = readDepthRange,
    mappingEfficiency = mappingEfficiency,
    multipletRate = multipletRate,
    multipletFactor = multipletFactor,
    min.UMI.counts = min.UMI.counts,
    perc.indiv.expr = perc.indiv.expr,
    samplingMethod = "quantiles",
    sign.threshold = sign.threshold,
    MTmethod = MTmethod,
    useSimulatedPower = useSimulatedPower,
    speedPowerCalc = speedPowerCalc,
    indepSNPs = indepSNPs,
    ssize.ratio.de = ssize.ratio.de,
    reactionsPerKit = reactionsPerKit
  )

  colnames(power.study.plot)[2]<-"Detection.power"

  # Convert the result to JSON
  result_json <- toJSON(power.study.plot, auto_unbox = TRUE)

  # Print the JSON result
  cat(result_json)
}, error = function(e) {
  cat("Error in optimize.constant.budget.restrictedDoublets: ", conditionMessage(e), "\n")
  quit(status = 1)
})