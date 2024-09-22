library(shinytest2)

test_that("{shinytest2} recording: scPower_shiny", {
  app <- AppDriver$new(variant = platform_variant(), name = "scPower_shiny", height = 912, 
      width = 1619)
  app$set_inputs(cost = c("FALSE", "FALSE", "FALSE", "FALSE", "orange", "TRUE", "0"))
  app$click("recalc")
  app$expect_values()
  app$expect_screenshot()
})
