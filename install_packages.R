# Restaurant Recommender - R Package Installation Script
# This script installs all required packages for the R Shiny application

# Set CRAN mirror
options(repos = c(CRAN = "https://cran.rstudio.com/"))

# List of required packages
required_packages <- c(
  # Core Shiny framework
  "shiny",
  "shinydashboard",
  "shinyjs",
  "shinyWidgets",
  
  # Data manipulation and analysis
  "dplyr",
  "tidyr",
  "stringr",
  "DBI",
  "RSQLite",
  
  # Machine learning and NLP
  "textrecipes",
  "parsnip",
  "workflows",
  "tune",
  "yardstick",
  "topicmodels",
  "tm",
  "text",
  "purrr",
  
  # Visualization
  "ggplot2",
  "plotly",
  "leaflet",
  "DT",
  "scales",
  "corrplot",
  "wordcloud2",
  "htmltools"
)

# Function to install packages if not already installed
install_if_missing <- function(packages) {
  for (pkg in packages) {
    if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
      cat(paste("Installing", pkg, "...\n"))
      install.packages(pkg, dependencies = TRUE)
    } else {
      cat(paste("✓", pkg, "already installed\n"))
    }
  }
}

# Print header
cat(paste(rep("=", 60), collapse = ""), "\n")
cat("🍽️ Restaurant Recommender - R Package Installation\n")
cat(paste(rep("=", 60), collapse = ""), "\n")
cat("Installing required packages for R Shiny application...\n\n")

# Install packages
install_if_missing(required_packages)

# Print completion message
cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("✅ Package installation complete!\n")
cat("You can now run the R Shiny app with:\n")
cat("  Rscript -e \"shiny::runApp('r-app/app.R', port=3838, host='127.0.0.1')\"\n")
cat(paste(rep("=", 60), collapse = ""), "\n")
