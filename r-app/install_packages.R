# Install required R packages for Restaurant Recommender
# Run this script to install all necessary packages

# Set CRAN mirror
options(repos = c(CRAN = "https://cran.rstudio.com/"))

# List of required packages
required_packages <- c(
  # Core Shiny packages
  "shiny",
  "shinydashboard", 
  "DT",
  "plotly",
  "leaflet",
  "shinycssloaders",
  "shinyWidgets",
  
  # Data manipulation and analysis
  "dplyr",
  "tidyr", 
  "stringr",
  "DBI",
  "RSQLite",
  
  # Text analysis and NLP
  "textrecipes",
  "tidymodels",
  "topicmodels",
  "text",
  "tm",
  "wordcloud2",
  
  # Visualization
  "ggplot2",
  "scales",
  "corrplot",
  "htmltools"
)

# Function to install packages if not already installed
install_if_missing <- function(packages) {
  for (pkg in packages) {
    if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
      cat("Installing", pkg, "...\n")
      install.packages(pkg, dependencies = TRUE)
      
      # Check if installation was successful
      if (require(pkg, character.only = TRUE, quietly = TRUE)) {
        cat("✅", pkg, "installed successfully\n")
      } else {
        cat("❌ Failed to install", pkg, "\n")
      }
    } else {
      cat("✅", pkg, "already installed\n")
    }
  }
}

# Install packages
cat("🚀 Installing R packages for Restaurant Recommender\n")
cat(paste(rep("=", 60), collapse = ""), "\n")

install_if_missing(required_packages)

cat("\n🎉 Package installation complete!\n")
cat("You can now run the R Shiny app with: shiny::runApp('app.R')\n")
