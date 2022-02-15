library(targets)
library(tarchetypes)
# This is an example _targets.R file. Every
# {targets} pipeline needs one.
# Use tar_script() to create _targets.R and tar_edit()
# to open it again for editing.
# Then, run tar_make() to run the pipeline
# and tar_read(summary) to view the results.

# Define custom functions and other global objects.
# This is where you write source(\"R/functions.R\")
# if you keep your functions in external scripts.


# Set target-specific options such as packages.
# tar_option_set(packages = "")

# End this file with a list of target objects.
list(
  tar_render(useful, "01_useful.Rmd", params = list(floor_bool = FALSE)),
  tar_render(eatonkortum, "02_eatonkortum.Rmd"),
  tar_render(expenditures, "03_expenditures.Rmd"),
  tar_render(tradecosts, "04_tradecosts.Rmd"),
  tar_render(counterfactual, "05_counterfactual.Rmd"),
  tar_render(artuc, "06_artuc.Rmd")
)
