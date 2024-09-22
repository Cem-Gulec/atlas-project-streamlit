library(shinytest2)
library(testthat)

Sys.setenv(NOT_CRAN = "true")

# Define the test
test_that("Headless recording: scPower_shiny", {
  # Create an AppDriver instance
  app <- AppDriver$new(
    app_dir = "scPower_shiny/",  # Replace with the actual path to your Shiny app
    variant = platform_variant(),
    name = "scPower_shiny",
    height = 962,
    width = 1598,
    load_timeout = 10000,  # Adjust timeout if needed
    view = FALSE  # Set to FALSE for headless mode
  )

  # Set inputs
  app$set_inputs(cost = c("FALSE", "FALSE", "FALSE", "FALSE", "orange", "TRUE", "0"))
  app$set_inputs(organism = "Homo sapiens")
  app$set_inputs(assay = "10x 3' v2")
  app$set_inputs(tissue = "breast")
  app$set_inputs(celltype = "macrophage (Assay: 10x 3' v2, Tissue: breast)")

  app$click("recalc")

  # Take snapshot of values
  app$expect_values()

  # Take screenshot
  app$expect_screenshot()

  # Close the app
  app$stop()
})