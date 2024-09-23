library(shinytest2)

test_that("{shinytest2} recording: scPower_shiny", {
  app <- AppDriver$new(variant = platform_variant(), name = "scPower_shiny", height = 993, 
      width = 1619)
  app$set_inputs(cost = c("FALSE", "FALSE", "FALSE", "FALSE", "orange", "TRUE", "0"))
  app$set_inputs(organism = "Homo sapiens")
  app$set_inputs(assay = "10x 3' v2")
  app$set_inputs(tissue = "breast")
  app$set_inputs(celltype = "macrophage (Assay: 10x 3' v2, Tissue: breast)")
  app$click("recalc")
  app$expect_values()
  app$expect_screenshot()
})
