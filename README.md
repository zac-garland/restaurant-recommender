
<!-- README.md is generated from README.Rmd. Please edit that file -->

# 🍽️ Restaurant Recommender

An intelligent restaurant recommendation system for Austin, TX featuring
advanced NLP techniques including BERT-based sentiment analysis, LDA
topic modeling, and semantic similarity matching. Available in both **R
Shiny** and **Python Shiny** implementations.

## 🚀 Quick Start

### Option 1: R Shiny Version

``` bash
# Install R packages
Rscript install_packages.R

# Run the app
cd r-app
Rscript -e "shiny::runApp('app.R', port=3838, host='127.0.0.1')"
```

**Access at:** <http://127.0.0.1:3838>

### Option 2: Python Shiny Version

``` bash
# Install Python dependencies
pip install -r requirements.txt

# Run the app
cd py-app
python -m shiny run app.py --port 8000 --host 127.0.0.1
```

**Access at:** <http://127.0.0.1:8000>

## ✨ Features

-   **🔍 Smart Search**: TF-IDF and BERT-based semantic similarity
-   **📊 Advanced Analytics**: LDA topic modeling and BERT sentiment
    analysis
-   **🗺️ Interactive Maps**: Rich popups with reviews, amenities, and
    contact info
-   **🎯 Click-to-Popup**: Click restaurant cards to show detailed map
    popups
-   **📱 Responsive Design**: Modern, mobile-friendly interface
-   **🛡️ Robust Error Handling**: Graceful fallbacks for all operations

## 🛠️ Technical Stack

### R Version

-   **Framework**: R Shiny
-   **NLP**: `textrecipes`, `topicmodels`, `tm`
-   **Visualization**: `leaflet`, `plotly`
-   **Data**: `tidyverse`, `DBI`, `RSQLite`

### Python Version

-   **Framework**: Shiny for Python
-   **NLP**: `transformers`, `sentence-transformers`, `scikit-learn`
-   **ML**: BERT models, LDA topic modeling
-   **Visualization**: `plotly`, `pandas`, `numpy`
-   **Data**: SQLite integration

## 📋 Detailed Setup Instructions

### Prerequisites

-   **R**: Version 4.0+ with RStudio (optional)
-   **Python**: Version 3.8+ with pip
-   **Database**: `austin_restaurants.db` (included in repository)

### R Shiny Setup

``` bash
# 1. Install R packages (run from project root)
Rscript install_packages.R

# 2. Navigate to R app directory
cd r-app

# 3. Run the application
Rscript -e "shiny::runApp('app.R', port=3838, host='127.0.0.1')"

# Alternative: Run with RStudio
# Open app.R in RStudio and click "Run App"
```

### Python Shiny Setup

``` bash
# 1. Create virtual environment (recommended)
python -m venv restaurant_env
source restaurant_env/bin/activate  # On Windows: restaurant_env\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Navigate to Python app directory
cd py-app

# 4. Run the application
python -m shiny run app.py --port 8000 --host 127.0.0.1
```

## 🎯 How to Use

1.  **Search**: Enter cuisine preferences (e.g., “romantic italian”,
    “barbecue”, “pizza”)
2.  **Browse**: View results in “Top Matches” with similarity scores
3.  **Explore**: Click restaurant cards to see detailed popups on the
    map
4.  **Analyze**: Check “Key Topics” and “Sentiment Analysis” for
    insights
5.  **Filter**: Use rating, cuisine, and dietary filters to narrow
    results

## 🔧 Advanced Features

### Search Methods

-   **TF-IDF**: Traditional text-based similarity
-   **BERT**: Semantic similarity using transformer models
-   **Hybrid**: Combines both approaches for optimal results

### Analytics Dashboard

-   **Topic Modeling**: LDA-based topic discovery from reviews
-   **Sentiment Analysis**: BERT-powered sentiment classification
-   **Rating Distribution**: Visual analytics of restaurant ratings

### Interactive Elements

-   **Rich Map Popups**: Reviews, amenities, contact info, photos
-   **Clickable Cards**: Visual feedback and map navigation
-   **Responsive Design**: Works on desktop, tablet, and mobile

## 🗂️ Project Structure

    restaurant.recommender/
    ├── README.Rmd                 # This file (source)
    ├── README.md                  # Generated from README.Rmd
    ├── requirements.txt           # Python dependencies
    ├── install_packages.R         # R package installer
    ├── austin_restaurants.db      # SQLite database
    ├── r-app/
    │   └── app.R                 # R Shiny application
    ├── py-app/
    │   └── app.py                # Python Shiny application
    ├── data/                     # Processed data files
    ├── figures/                  # Documentation images
    └── notes/                    # Development notes

# Example map of the underlying data

<img src="figures/example_map.png" width="100%" />

## Data Source

Data was scraped via the Google Places API and stored in a sql lite
database. Below are examples of accessing the data via R and Python

``` r
library(tidyverse)
library(RSQLite)

con <- dbConnect(RSQLite::SQLite(), "austin_restaurants.db")

dbListTables(con)
#> [1] "photos"        "place_details" "restaurants"   "reviews"
```

All tables join on the restaurant id which is called `id` in each table.

``` r
sql_example <- tbl(con,"restaurants") %>% 
  filter(business_status == "OPERATIONAL",!sql("lower(place_tags) like '%convenience%'")) %>% 
  select(name,id,rating,price_level,user_ratings_total,lat,lng,address,place_tags) %>% 
  head(10)

sql_example %>% collect() %>% print()
#> # A tibble: 10 x 9
#>    name          id    rating price_level user_ratings_total   lat   lng address
#>    <chr>         <chr>  <dbl>       <dbl>              <dbl> <dbl> <dbl> <chr>  
#>  1 Onion Creek ~ ChIJ~    4.3          NA                195  30.1 -97.8 2510 O~
#>  2 CraigO's Piz~ ChIJ~    4.1           1                363  30.1 -97.8 11215 ~
#>  3 Oyasumi Ramen ChIJ~    2.8          NA                 15  30.1 -97.8 11215 ~
#>  4 Cabo Bob's B~ ChIJ~    4.4           1                212  30.1 -97.8 11215 ~
#>  5 Sonic Drive-~ ChIJ~    3.7           1                870  30.2 -97.8 9916 B~
#>  6 Bowie Culina~ ChIJ~    4.8          NA                  9  30.2 -97.9 4103 W~
#>  7 Galaxy Cafe   ChIJ~    4.3           2                882  30.2 -97.8 9911 B~
#>  8 Maudie's Hac~ ChIJ~    4.3           2               1840  30.2 -97.8 9911 B~
#>  9 Wok On Fire   ChIJ~    3.2           2                270  30.2 -97.8 9901 B~
#> 10 Taco Bell     ChIJ~    3.2           1                561  30.2 -97.8 3324 W~
#> # i 1 more variable: place_tags <chr>
sql_example %>% show_query()
#> <SQL>
#> SELECT
#>   `name`,
#>   `id`,
#>   `rating`,
#>   `price_level`,
#>   `user_ratings_total`,
#>   `lat`,
#>   `lng`,
#>   `address`,
#>   `place_tags`
#> FROM `restaurants`
#> WHERE
#>   (`business_status` = 'OPERATIONAL') AND
#>   (NOT(lower(place_tags) like '%convenience%'))
#> LIMIT 10
```

``` python
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text

# Option 1: Using sqlite3 (built-in)
con = sqlite3.connect("austin_restaurants.db")

# List tables
cursor = con.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# SQL query equivalent
query = """
SELECT 
    name,
    id,
    rating,
    price_level,
    user_ratings_total,
    lat,
    lng,
    address,
    place_tags
FROM restaurants
WHERE business_status = 'OPERATIONAL'
    AND lower(place_tags) NOT LIKE '%convenience%'
LIMIT 10
"""

sql_example = pd.read_sql_query(query, con)
print(sql_example)

con.close()
```

## 🚨 Troubleshooting

### Common Issues

#### R Version

-   **Package Installation**: Run `Rscript install_packages.R` from
    project root
-   **Port Conflicts**: Change port in run command (e.g., `port=3839`)
-   **Memory Issues**: Close other R sessions and restart R

#### Python Version

-   **Virtual Environment**: Always use a virtual environment for
    dependencies
-   **PyTorch Issues**: Install PyTorch separately if needed:
    `pip install torch`
-   **Port Conflicts**: Change port in run command (e.g., `--port 8001`)

### Performance Notes

-   **BERT Models**: First run downloads pre-trained models (\~500MB)
-   **Large Dataset**: App uses 3,566 restaurants and 16,509 reviews
-   **Memory Usage**: \~2GB RAM recommended for optimal performance

## 🔬 Development

### Contributing

1.  Fork the repository
2.  Create a feature branch
3.  Make changes to either R or Python version
4.  Test thoroughly
5.  Submit a pull request

### Code Structure

-   **R Version**: Single `app.R` file with modular functions
-   **Python Version**: Single `app.py` file with class-based
    organization
-   **Database**: SQLite with restaurants, reviews, and place\_details
    tables

### Testing

``` bash
# Test R version
cd r-app
Rscript -e "source('app.R', local=TRUE); load_data()"

# Test Python version
cd py-app
python -c "from app import load_data; load_data()"
```

## 📊 Data Schema

The SQLite database contains three main tables:

-   **restaurants**: Basic restaurant information (name, rating,
    location, etc.)
-   **reviews**: User reviews with text and ratings
-   **place\_details**: Extended details (amenities, contact info, etc.)

All tables join on the `id` field (restaurant identifier).

``` r
library(tidyverse)
library(leaflet)
library(DBI)
library(RSQLite)

# Connect to database
con <- dbConnect(RSQLite::SQLite(), "austin_restaurants.db")

restaurants <- tbl(con, "restaurants") %>%
  filter(business_status == "OPERATIONAL") %>%
  collect() 

dbDisconnect(con)

# Create price level labels
restaurants <- restaurants %>%
  mutate(
    price_label = case_when(
      price_level == 1 ~ "$",
      price_level == 2 ~ "$$",
      price_level == 3 ~ "$$$",
      price_level == 4 ~ "$$$$",
      TRUE ~ "Unknown"
    ),
    price_color = case_when(
      price_level == 1 ~ "#27ae60",
      price_level == 2 ~ "#f39c12",
      price_level == 3 ~ "#e74c3c",
      price_level == 4 ~ "#8e44ad",
      TRUE ~ "gray"
    )
  )


leaflet(restaurants) %>%
  addTiles() %>%
  addCircleMarkers(
    lng = ~lng,
    lat = ~lat,
    radius = ~rating * 1.5,
    color = ~price_color,
    fillColor = ~price_color,
    fillOpacity = 0.6,
    stroke = TRUE,
    weight = 1,
    popup = ~paste0(
      "<b>", name, "</b><br/>",
      "Price: ", price_label, "<br/>",
      "Rating: ", rating, " (", user_ratings_total, " reviews)<br/>",
      "Address: ", address
    ),
    label = ~name
  ) %>%
  addLegend(
    position = "bottomright",
    colors = c("#27ae60", "#f39c12", "#e74c3c", "#8e44ad"),
    labels = c("$", "$$", "$$$", "$$$$"),
    title = "Price Level",
    opacity = 0.8
  )
```
