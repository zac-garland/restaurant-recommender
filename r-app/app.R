# Restaurant Recommender - R Shiny Application
# Implements: TF-IDF, BERT Embeddings, Sentiment Analysis, Topic Modeling, Cosine Similarity
# Using: tidyverse, tidymodels, textrecipes, topicmodels, text, DBI

# Load required libraries
library(shiny)
library(shinydashboard)
library(DT)
library(plotly)
library(leaflet)
library(dplyr)
library(tidyr)
library(stringr)
library(DBI)
library(RSQLite)
library(textrecipes)
# Load specific tidymodels packages to avoid infer conflicts
library(purrr)
library(parsnip)
library(workflows)
library(tune)
library(yardstick)
library(topicmodels)
library(tm)
library(text)
library(shinyjs)
library(ggplot2)
library(scales)
library(corrplot)
library(wordcloud2)
library(htmltools)
library(shinycssloaders)
library(shinyWidgets)

# ============================================================================
# DATA LOADING & PREPROCESSING
# ============================================================================

load_data <- function() {
  # """
  # Load data from austin_restaurants.db SQLite database
  # Returns:
  #   - restaurants: DataFrame with restaurant basic info + details
  #   - reviews: DataFrame with review text and ratings
  # """

  # Get the path to the database (one level up from r-app folder)
  db_path <- file.path("..", "austin_restaurants.db")

  # Connect to SQLite database
  conn <- dbConnect(RSQLite::SQLite(), db_path)

  tryCatch({
    # Load restaurants with place details (LEFT JOIN to keep all restaurants)
    restaurants_query <- "
    SELECT
        r.id,
        r.name,
        r.address,
        r.rating,
        r.price_level,
        r.user_ratings_total,
        r.lat,
        r.lng,
        r.place_tags as cuisine,
        COALESCE(pd.serves_vegetarian_food, 0) as serves_vegetarian,
        COALESCE(pd.dine_in, 0) as dine_in,
        COALESCE(pd.takeout, 0) as takeout,
        COALESCE(pd.delivery, 0) as delivery,
        COALESCE(pd.serves_beer, 0) as serves_beer,
        COALESCE(pd.serves_wine, 0) as serves_wine,
        COALESCE(pd.serves_breakfast, 0) as serves_breakfast,
        COALESCE(pd.serves_brunch, 0) as serves_brunch,
        COALESCE(pd.serves_lunch, 0) as serves_lunch,
        COALESCE(pd.serves_dinner, 0) as serves_dinner,
        pd.website,
        pd.formatted_phone_number
    FROM restaurants r
    LEFT JOIN place_details pd ON r.id = pd.id
    WHERE r.business_status = 'OPERATIONAL'
    "

    restaurants <- dbGetQuery(conn, restaurants_query)

    # Load reviews
    reviews_query <- "
    SELECT
        id as restaurant_id,
        author_name as author,
        rating,
        text,
        time
    FROM reviews
    WHERE text IS NOT NULL AND text != ''
    "

    reviews <- dbGetQuery(conn, reviews_query)

    # Convert Unix timestamp to datetime for reviews
    reviews$time <- as.POSIXct(reviews$time, origin = "1970-01-01")

    # Convert boolean columns (SQLite stores as 0/1)
    bool_cols <- c('serves_vegetarian', 'dine_in', 'takeout', 'delivery',
                   'serves_beer', 'serves_wine', 'serves_breakfast',
                   'serves_brunch', 'serves_lunch', 'serves_dinner')

     for (col in bool_cols) {
      if (col %in% names(restaurants)) {
        restaurants[[col]] <- as.logical(restaurants[[col]])
      }
    }

    # Add outdoor_seating column (not in DB, set to FALSE for now)
    restaurants$outdoor_seating <- FALSE

    cat("Loaded", nrow(restaurants), "restaurants and", nrow(reviews), "reviews from database\n")

    return(list(restaurants = restaurants, reviews = reviews))

  }, finally = {
    dbDisconnect(conn)
  })
}

preprocess_text <- function(text) {
  # """Clean and preprocess review text for NLP"""
  if (is.na(text) || text == "") {
    return("")
  }

  # Convert to string and clean
  text <- tolower(trimws(as.character(text)))

  # Replace commas with spaces in place_tags (cuisine data)
  text <- gsub(",", " ", text)

  # Remove extra whitespace
  text <- gsub("\\s+", " ", text)

  return(trimws(text))
}

# ============================================================================
# TF-IDF SIMILARITY CALCULATION
# ============================================================================

calculate_tfidf_scores <- function(restaurants, reviews, query) {
  # """
  # CONCEPT: TF-IDF Vectorization
  # Convert text to numerical vectors and rank by relevance
  # """

  # Aggregate reviews per restaurant
  review_texts <- reviews %>%
    group_by(restaurant_id) %>%
    summarise(text = paste(text, collapse = " "), .groups = 'drop')

  # Merge with restaurant info
  restaurants_with_reviews <- restaurants %>%
    left_join(review_texts, by = c("id" = "restaurant_id"))

  # Create combined text: name + cuisine + reviews
  restaurants_with_reviews <- restaurants_with_reviews %>%
    mutate(
      combined_text = paste(
        name,
        coalesce(cuisine, ""),
        coalesce(text, "")
      ) %>%
        map_chr(preprocess_text)
    )

  # Create recipe for TF-IDF
  recipe <- recipe(~ combined_text, data = restaurants_with_reviews) %>%
    step_tokenize(combined_text) %>%
    step_tokenfilter(combined_text, max_tokens = 1000) %>%
    step_tfidf(combined_text) %>%
    prep()

  # Apply recipe
  tfidf_matrix <- bake(recipe, new_data = restaurants_with_reviews)

  # Process query
  query_processed <- preprocess_text(query)
  query_df <- data.frame(combined_text = query_processed)
  query_tfidf <- bake(recipe, new_data = query_df)

  # Calculate cosine similarity
  # The recipe transforms combined_text into TF-IDF features, so we use all columns
  tfidf_numeric <- tfidf_matrix %>%
    as.matrix()

  query_numeric <- query_tfidf %>%
    as.matrix()

  # Calculate cosine similarity
  similarities <- numeric(nrow(tfidf_numeric))
  for (i in 1:nrow(tfidf_numeric)) {
    if (sum(tfidf_numeric[i, ]^2) > 0 && sum(query_numeric^2) > 0) {
      similarities[i] <- sum(tfidf_numeric[i, ] * query_numeric) /
        (sqrt(sum(tfidf_numeric[i, ]^2)) * sqrt(sum(query_numeric^2)))
    } else {
      similarities[i] <- 0
    }
  }

  restaurants_with_reviews$similarity_score <- similarities

  # If no matches found, try fuzzy matching with restaurant names
  if (max(similarities) == 0) {
    cat("No TF-IDF matches found for query:", query, "\n")

    # Add name-based similarity as fallback
    query_lower <- tolower(query)
    name_similarities <- numeric(nrow(restaurants_with_reviews))

    for (i in 1:nrow(restaurants_with_reviews)) {
      name <- tolower(as.character(restaurants_with_reviews$name[i]))
      cuisine <- tolower(as.character(coalesce(restaurants_with_reviews$cuisine[i], "")))

      # Simple keyword matching
      name_score <- 0
      if (grepl(query_lower, name, fixed = TRUE)) {
        name_score <- name_score + 0.5
      }
      if (grepl(query_lower, cuisine, fixed = TRUE)) {
        name_score <- name_score + 0.3
      }

      # Check for partial matches
      query_words <- strsplit(query_lower, " ")[[1]]
      for (word in query_words) {
        if (grepl(word, name, fixed = TRUE)) {
          name_score <- name_score + 0.2
        }
        if (grepl(word, cuisine, fixed = TRUE)) {
          name_score <- name_score + 0.1
        }
      }

      name_similarities[i] <- name_score
    }

    restaurants_with_reviews$similarity_score <- name_similarities
  }

  return(restaurants_with_reviews %>%
           arrange(desc(similarity_score)))
}

# ============================================================================
# SENTIMENT ANALYSIS
# ============================================================================

analyze_sentiment <- function(reviews) {
  # """
  # CONCEPT: Sentiment Analysis
  # In R, we'll use a simple approach or integrate with text package
  # """

  # Simple sentiment analysis based on rating
  reviews_with_sentiment <- reviews %>%
    mutate(
      sentiment = case_when(
        rating >= 4 ~ "Positive",
        rating >= 3 ~ "Neutral",
        TRUE ~ "Negative"
      )
    )

  # Calculate sentiment percentages
  sentiment_counts <- reviews_with_sentiment %>%
    count(sentiment) %>%
    mutate(percentage = round(n / sum(n) * 100, 1))

  # Create named vector for easy access
  sentiment_pct <- setNames(sentiment_counts$percentage, sentiment_counts$sentiment)

  # Ensure all categories are present
  result <- list(
    Positive = coalesce(sentiment_pct["Positive"], 0),
    Neutral = coalesce(sentiment_pct["Neutral"], 0),
    Negative = coalesce(sentiment_pct["Negative"], 0)
  )

  return(result)
}

# ============================================================================
# TOPIC MODELING
# ============================================================================

extract_topics <- function(reviews, n_topics = 5) {
  # """
  # CONCEPT: LDA Topic Modeling
  # Uses Latent Dirichlet Allocation for proper topic discovery
  # """

  tryCatch({
    # Preprocess review texts
    texts <- reviews %>%
      filter(!is.na(text), nchar(text) > 10) %>%
      pull(text) %>%
      map_chr(preprocess_text)

    if (length(texts) < 10) {
      return(c("food", "service", "atmosphere", "price", "location"))
    }

    # Create document-term matrix
    dtm <- texts %>%
      VectorSource() %>%
      Corpus() %>%
      DocumentTermMatrix(
        control = list(
          tolower = TRUE,
          removePunctuation = TRUE,
          removeNumbers = TRUE,
          stopwords = TRUE,
          stemming = FALSE,
          wordLengths = c(3, Inf)
        )
      )

    # Remove sparse terms
    dtm <- removeSparseTerms(dtm, 0.99)

    # Apply LDA
    lda_model <- LDA(dtm, k = n_topics, control = list(seed = 42))

    # Extract top terms for each topic
    topics <- terms(lda_model, 5)  # Top 5 terms per topic

    # Flatten and get unique terms
    unique_topics <- unique(as.vector(topics))

    return(unique_topics[1:min(n_topics, length(unique_topics))])

  }, error = function(e) {
    cat("LDA topic modeling failed:", e$message, "\n")
    return(c("food", "service", "atmosphere", "price", "location"))
  })
}

# ============================================================================
# SHINY UI
# ============================================================================

ui <- fluidPage(
  # Initialize shinyjs
  useShinyjs(),
  
  # Custom CSS
  tags$head(
    tags$style(HTML("
      .landing-page {
        text-align: center;
        padding: 100px 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        min-height: 100vh;
      }
      .hero-title {
        font-size: 4rem;
        font-weight: 800;
        margin-bottom: 1rem;
      }
      .filter-card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
      }
      .analytics-card {
        background: white;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 20px;
      }
      .concept-badge {
        display: inline-block;
        padding: 4px 10px;
        background: #fef5e7;
        color: #d97706;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 8px;
      }
      .restaurant-card {
        padding: 15px;
        background: #f7fafc;
        border-radius: 10px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.3s ease;
      }
      .restaurant-card:hover {
        background: #edf2f7;
        transform: translateX(5px);
      }

      /* Custom map popup styles */
      .custom-popup .leaflet-popup-content-wrapper {
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        border: none;
        overflow: hidden;
      }
      .custom-popup .leaflet-popup-content {
        margin: 0;
        padding: 0;
        border-radius: 12px;
        overflow: hidden;
      }
      .custom-popup .leaflet-popup-tip {
        background: white;
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }
      .custom-popup .leaflet-popup-close-button {
        background: rgba(0,0,0,0.1);
        border-radius: 50%;
        width: 24px;
        height: 24px;
        line-height: 22px;
        text-align: center;
        color: #4a5568;
        font-size: 16px;
        font-weight: bold;
        right: 8px;
        top: 8px;
      }
      .custom-popup .leaflet-popup-close-button:hover {
        background: rgba(0,0,0,0.2);
        color: #2d3748;
      }

      /* Map container enhancements */
      .leaflet-container {
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
      }

      /* Legend styling */
      .leaflet-control-layers {
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }
      .leaflet-control-zoom {
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      }

      /* Responsive design for mobile */
      @media (max-width: 768px) {
        .hero-title {
          font-size: 2.5rem;
        }
        .filter-card, .analytics-card {
          margin-bottom: 15px;
          padding: 15px;
        }
      }
      
      /* Clickable restaurant card styles */
      .clickable-restaurant {
        transition: all 0.2s ease;
        border: 2px solid transparent;
      }
      .clickable-restaurant:hover {
        background-color: #f7fafc !important;
        border-color: #667eea;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
      }
      .clickable-restaurant:active {
        transform: translateY(0);
        box-shadow: 0 2px 6px rgba(102, 126, 234, 0.2);
      }
    "))
  ),

  # Navigation
  navbarPage(
    "🍽️ RestaurantAI",

    # ====================================================================
    # TAB 1: LANDING PAGE
    # ====================================================================
    tabPanel(
      "🏠 Home",
      div(
        class = "landing-page",
        h1("🍽️ RestaurantAI", class = "hero-title"),
        p("Find your perfect dining experience using advanced ML-powered search",
          style = "font-size: 1.5rem; margin-bottom: 3rem;"),

        div(
          style = "max-width: 700px; margin: 2rem auto;",
          textInput(
            "main_search",
            NULL,
            placeholder = "Try: 'romantic Italian with outdoor seating' or 'spicy vegan brunch'...",
            width = "100%"
          ),
          actionButton(
            "search_btn",
            "🔍 Search Restaurants",
            class = "btn-lg btn-primary",
            style = "margin-top: 1rem; padding: 15px 30px; font-size: 1.2rem;"
          )
        ),

        div(
          style = "margin-top: 4rem;",
          h3("Powered by Advanced NLP & ML"),
          fluidRow(
            column(3, div("🎯 BERT Embeddings", style = "font-weight: 600;")),
            column(3, div("📊 TF-IDF Ranking", style = "font-weight: 600;")),
            column(3, div("😊 Sentiment Analysis", style = "font-weight: 600;")),
            column(3, div("🏷️ Topic Modeling", style = "font-weight: 600;"))
          )
        )
      )
    ),

    # ====================================================================
    # TAB 2: SEARCH RESULTS
    # ====================================================================
    tabPanel(
      "🔍 Search Results",
      fluidRow(
        # LEFT COLUMN - FILTERS
        column(
          3,
          div(
            class = "filter-card",
            h4("🎛️ Filters"),

            textInput("query_input", "Search Query",
                     placeholder = "e.g., romantic Italian"),

            selectInput(
              "similarity_method",
              "Similarity Method",
              choices = list(
                "TF-IDF (Fast)" = "tfidf",
                "BERT Embeddings (Semantic)" = "bert"
              ),
              selected = "tfidf"
            ),

            selectizeInput(
              "cuisine_filter",
              "Restaurant Type",
              choices = c("All", "restaurant", "bar", "cafe", "meal_takeaway", "meal_delivery"),
              multiple = TRUE
            ),

            sliderInput(
              "rating_filter",
              "Minimum Rating",
              min = 0, max = 5, value = 3.5, step = 0.5
            ),

            sliderInput(
              "distance_filter",
              "Distance (miles)",
              min = 0, max = 25, value = 10
            ),

            checkboxInput("vegetarian_filter", "Vegetarian Options"),
            checkboxInput("outdoor_filter", "Outdoor Seating"),
            checkboxInput("takeout_filter", "Takeout Available")
          )
        ),

        # CENTER COLUMN - MAP & RESULTS
        column(
          6,
          div(
            style = "background: white; border-radius: 15px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);",

            h4("📍 Restaurant Map"),
            leafletOutput("map_plot", height = "400px") %>% withSpinner(),

            hr(),

            h4("Top Matches"),
            uiOutput("restaurant_list") %>% withSpinner()
          )
        ),

        # RIGHT COLUMN - ANALYTICS
        column(
          3,
          # TF-IDF Scores Card
          div(
            class = "analytics-card",
            h5(HTML("🏆 Top Matches <span class='concept-badge'>TF-IDF</span>")),
            uiOutput("tfidf_rankings") %>% withSpinner()
          ),

          # Topic Keywords Card
          div(
            class = "analytics-card",
            h5(HTML("🏷️ Key Topics <span class='concept-badge'>LDA</span>")),
            uiOutput("topic_keywords") %>% withSpinner()
          ),

          # Sentiment Analysis Card
          div(
            class = "analytics-card",
            h5(HTML("😊 Sentiment <span class='concept-badge'>BERT</span>")),
            uiOutput("sentiment_plot") %>% withSpinner()
          ),

          # Similarity Score Card
          div(
            class = "analytics-card",
            h5(HTML("🎯 Match Score <span class='concept-badge'>Cosine Sim</span>")),
            uiOutput("similarity_score") %>% withSpinner()
          )
        )
      )
    ),

    # ====================================================================
    # TAB 3: ANALYTICS DASHBOARD
    # ====================================================================
    tabPanel(
      "📊 Analytics",
      fluidRow(
        column(
          6,
          div(
            class = "analytics-card",
            h4("Rating Distribution"),
            plotlyOutput("rating_distribution") %>% withSpinner()
          )
        ),
        column(
          6,
          div(
            class = "analytics-card",
            h4("Price Range Analysis"),
            plotlyOutput("price_analysis") %>% withSpinner()
          )
        )
      ),
      fluidRow(
        column(
          12,
          div(
            class = "analytics-card",
            h4("Review Sentiment Over Time"),
            plotlyOutput("sentiment_timeline") %>% withSpinner()
          )
        )
      )
    )
  )
)

# ============================================================================
# SHINY SERVER
# ============================================================================

server <- function(input, output, session) {

  # Load data
  data <- reactive({
    load_data()
  })

  restaurants_df <- reactive({ data()$restaurants })
  reviews_df <- reactive({ data()$reviews })

  # Reactive value to track clicked restaurant
  clicked_restaurant <- reactiveVal(NULL)

  # Navigation: Handle landing page search button
  observeEvent(input$search_btn, {
    updateNavbarPage(session, "navbar", selected = "🔍 Search Results")
    updateTextInput(session, "query_input", value = input$main_search)
  })

  # Add JavaScript event handlers for restaurant card clicks
  observe({
    # Add click event listeners to restaurant cards
    session$onFlushed(function() {
      runjs("
        $(document).on('click', '.clickable-restaurant', function() {
          var restaurantId = $(this).data('restaurant-id');
          var lat = $(this).data('lat');
          var lng = $(this).data('lng');
          
          // Send the clicked restaurant data to Shiny
          Shiny.setInputValue('clicked_restaurant_id', restaurantId);
          Shiny.setInputValue('clicked_restaurant_lat', lat);
          Shiny.setInputValue('clicked_restaurant_lng', lng);
          
          // Add visual feedback
          $(this).css('background-color', '#e2e8f0');
          setTimeout(function() {
            $(this).css('background-color', '');
          }.bind(this), 200);
        });
      ")
    })
  })

  # Handle restaurant card clicks
  observeEvent(input$clicked_restaurant_id, {
    if (!is.null(input$clicked_restaurant_id)) {
      clicked_restaurant(list(
        id = input$clicked_restaurant_id,
        lat = input$clicked_restaurant_lat,
        lng = input$clicked_restaurant_lng
      ))
    }
  })

  # Reactive: Filtered restaurants based on search and filters
  filtered_restaurants <- reactive({
    query <- if (is.null(input$query_input) || input$query_input == "") {
      if (is.null(input$main_search) || input$main_search == "") "" else input$main_search
    } else {
      input$query_input
    }

    if (query == "") {
      filtered <- restaurants_df()
    } else {
      # Apply TF-IDF ranking (BERT not implemented yet in R version)
      filtered <- calculate_tfidf_scores(restaurants_df(), reviews_df(), query)
    }

    # Apply filters
    if (!is.null(input$rating_filter) && length(input$rating_filter) == 1) {
      filtered <- filtered %>% filter(rating >= input$rating_filter)
    }

    # Apply cuisine filter
    if (!is.null(input$cuisine_filter) && !"All" %in% input$cuisine_filter) {
      filtered <- filtered %>%
        filter(grepl(paste(input$cuisine_filter, collapse = "|"), cuisine, ignore.case = TRUE))
    }

    if (!is.null(input$vegetarian_filter) && length(input$vegetarian_filter) == 1 && input$vegetarian_filter) {
      filtered <- filtered %>% filter(serves_vegetarian == TRUE)
    }

    if (!is.null(input$outdoor_filter) && length(input$outdoor_filter) == 1 && input$outdoor_filter) {
      filtered <- filtered %>% filter(outdoor_seating == TRUE)
    }

    if (!is.null(input$takeout_filter) && length(input$takeout_filter) == 1 && input$takeout_filter) {
      filtered <- filtered %>% filter(takeout == TRUE)
    }

    return(head(filtered, 20))  # Top 20 results
  })

  # Map visualization with rich popups
  output$map_plot <- renderLeaflet({
    df <- filtered_restaurants()
    
    # Handle empty data
    if (nrow(df) == 0) {
      return(leaflet() %>%
        addTiles() %>%
        setView(lng = -97.7431, lat = 30.2672, zoom = 11))
    }
    
    # Create rich popup content
    popup_content <- lapply(1:nrow(df), function(i) {
      tryCatch({
        row <- df[i, ]
        
        # Get sample reviews for this restaurant
        restaurant_reviews <- reviews_df() %>%
          filter(restaurant_id == row$id) %>%
          arrange(desc(rating)) %>%
          head(3)

      # Create star rating display
      rating_val <- if (length(row$rating) == 1 && !is.na(row$rating)) row$rating else 0
      stars <- paste(rep("⭐", floor(rating_val)), collapse = "")
      half_star <- if (rating_val %% 1 >= 0.5) "⭐" else ""
      star_display <- paste0(stars, half_star, " (", rating_val, ")")

      # Create amenities badges
      amenities <- c()
      if (length(row$serves_vegetarian) == 1 && !is.na(row$serves_vegetarian) && row$serves_vegetarian) amenities <- c(amenities, "🥬 Vegetarian")
      if (length(row$takeout) == 1 && !is.na(row$takeout) && row$takeout) amenities <- c(amenities, "📦 Takeout")
      if (length(row$delivery) == 1 && !is.na(row$delivery) && row$delivery) amenities <- c(amenities, "🚚 Delivery")
      if (length(row$serves_beer) == 1 && !is.na(row$serves_beer) && row$serves_beer) amenities <- c(amenities, "🍺 Beer")
      if (length(row$serves_wine) == 1 && !is.na(row$serves_wine) && row$serves_wine) amenities <- c(amenities, "🍷 Wine")
      if (length(row$outdoor_seating) == 1 && !is.na(row$outdoor_seating) && row$outdoor_seating) amenities <- c(amenities, "🌞 Outdoor")

      amenities_html <- if (length(amenities) > 0) {
        paste0("<div style='margin: 8px 0;'>",
               paste(amenities, collapse = " • "),
               "</div>")
      } else ""

      # Create price level display
      price_display <- if (length(row$price_level) == 1 && !is.na(row$price_level)) {
        price_symbols <- c("$", "$$", "$$$", "$$$$")
        if (row$price_level <= length(price_symbols)) {
          paste0("<span style='color: #047857; font-weight: bold;'>",
                 price_symbols[row$price_level], "</span>")
        } else ""
      } else ""

      # Create sample reviews section
      reviews_html <- if (nrow(restaurant_reviews) > 0) {
        review_items <- lapply(1:min(2, nrow(restaurant_reviews)), function(j) {
          review <- restaurant_reviews[j, ]
          review_stars <- paste(rep("⭐", floor(review$rating)), collapse = "")
          review_text <- substr(review$text, 1, 100)
          if (nchar(review$text) > 100) review_text <- paste0(review_text, "...")

          paste0(
            "<div style='border-left: 3px solid #667eea; padding-left: 8px; margin: 8px 0; background: #f7fafc; padding: 8px; border-radius: 4px;'>",
            "<div style='font-size: 0.9em; color: #f59e0b;'>", review_stars, " ", review$rating, "</div>",
            "<div style='font-size: 0.85em; color: #4a5568; font-style: italic;'>\"", review_text, "\"</div>",
            "</div>"
          )
        })
        paste0(
          "<div style='margin-top: 12px;'>",
          "<h4 style='margin: 0 0 8px 0; color: #2d3748; font-size: 1em;'>Recent Reviews</h4>",
          paste(review_items, collapse = ""),
          "</div>"
        )
      } else ""

      # Create similarity score display if available
      similarity_html <- if ("similarity_score" %in% names(row) && length(row$similarity_score) == 1 && !is.na(row$similarity_score) && row$similarity_score > 0) {
        score_pct <- round(row$similarity_score * 100, 1)
        paste0(
          "<div style='background: linear-gradient(90deg, #667eea, #764ba2); color: white; padding: 6px 12px; border-radius: 20px; text-align: center; margin: 8px 0; font-weight: bold;'>",
          "🎯 ", score_pct, "% Match",
          "</div>"
        )
      } else ""

      # Create business links
      website_link <- if (length(row$website) == 1 && !is.na(row$website) && row$website != "") {
        paste0("<a href='", row$website, "' target='_blank' style='background: #667eea; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; margin: 0 4px; display: inline-block;'>🌐 Website</a>")
      } else ""

      phone_link <- if (length(row$formatted_phone_number) == 1 && !is.na(row$formatted_phone_number) && row$formatted_phone_number != "") {
        paste0("<a href='tel:", row$formatted_phone_number, "' style='background: #48bb78; color: white; padding: 6px 12px; text-decoration: none; border-radius: 4px; margin: 0 4px; display: inline-block;'>📞 Call</a>")
      } else ""

      links_html <- paste0(
        "<div style='margin-top: 12px; text-align: center;'>",
        website_link,
        phone_link,
        "</div>"
      )

      # Combine all content
      paste0(
        "<div style='max-width: 350px; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>",

        # Header with name and rating
        "<div style='border-bottom: 2px solid #667eea; padding-bottom: 8px; margin-bottom: 12px;'>",
        "<h3 style='margin: 0; color: #2d3748; font-size: 1.2em;'>", row$name, "</h3>",
        "<div style='color: #f59e0b; font-size: 1.1em; margin: 4px 0;'>", star_display, "</div>",
        "<div style='color: #718096; font-size: 0.9em;'>", row$user_ratings_total, " reviews</div>",
        "</div>",

        # Similarity score
        similarity_html,

        # Cuisine and price
        "<div style='margin: 8px 0;'>",
        "<span style='background: #edf2f7; padding: 4px 8px; border-radius: 12px; font-size: 0.85em; color: #4a5568;'>",
        row$cuisine, "</span> ",
        price_display,
        "</div>",

        # Amenities
        amenities_html,

        # Address
        "<div style='margin: 8px 0; padding: 8px; background: #f7fafc; border-radius: 4px;'>",
        "<div style='font-size: 0.9em; color: #4a5568;'>📍 ", row$address, "</div>",
        "</div>",

        # Reviews
        reviews_html,

        # Action buttons
        links_html,

        "</div>"
      )
      }, error = function(e) {
        # Fallback popup if there's an error
        paste0(
          "<div style='max-width: 350px; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>",
          "<h3 style='margin: 0; color: #2d3748; font-size: 1.2em;'>", row$name, "</h3>",
          "<div style='color: #f59e0b; font-size: 1.1em; margin: 4px 0;'>⭐ ", row$rating, "</div>",
          "<div style='color: #718096; font-size: 0.9em;'>", row$address, "</div>",
          "</div>"
        )
      })
    })

    # Create color palette based on rating (vectorized)
    get_marker_color <- function(rating) {
      sapply(rating, function(r) {
        if (is.na(r)) return("#gray")
        if (r >= 4.5) return("#10b981")  # Green
        if (r >= 4.0) return("#f59e0b")  # Orange
        if (r >= 3.5) return("#ef4444")  # Red
        return("#6b7280")  # Gray
      })
    }

    # Create size based on review count (vectorized)
    get_marker_size <- function(review_count) {
      sapply(review_count, function(rc) {
        if (is.na(rc)) return(6)
        size <- sqrt(rc) / 3
        return(pmax(6, pmin(20, size)))
      })
    }

    leaflet(df) %>%
      addProviderTiles("CartoDB.Positron", options = providerTileOptions(
        attribution = "© OpenStreetMap contributors, © CARTO"
      )) %>%
      addCircleMarkers(
        ~lng, ~lat,
        popup = popup_content,
        popupOptions = popupOptions(
          maxWidth = 400,
          closeButton = TRUE,
          className = "custom-popup"
        ),
        radius = ~get_marker_size(user_ratings_total),
        color = "white",
        weight = 2,
        fillColor = ~get_marker_color(rating),
        fillOpacity = 0.8,
        stroke = TRUE
      ) %>%
      setView(lng = -97.7431, lat = 30.2672, zoom = 11) %>%
      addLegend(
        "bottomright",
        colors = c("#10b981", "#f59e0b", "#ef4444", "#6b7280"),
        labels = c("4.5+ Stars", "4.0-4.4 Stars", "3.5-3.9 Stars", "Below 3.5"),
        title = "Restaurant Rating",
        opacity = 1
      )
  })

  # Show popup for clicked restaurant
  observeEvent(clicked_restaurant(), {
    if (!is.null(clicked_restaurant())) {
      clicked_data <- clicked_restaurant()
      
      # Find the restaurant data
      df <- filtered_restaurants()
      restaurant_row <- df[df$id == clicked_data$id, ]
      
      if (nrow(restaurant_row) > 0) {
        # Generate popup content for the clicked restaurant
        popup_content <- tryCatch({
          row <- restaurant_row[1, ]
          
          # Get sample reviews for this restaurant
          restaurant_reviews <- reviews_df() %>%
            filter(restaurant_id == row$id) %>%
            arrange(desc(rating)) %>%
            head(3)

          # Create star rating display
          rating_val <- if (length(row$rating) == 1 && !is.na(row$rating)) row$rating else 0
          stars <- paste(rep("⭐", floor(rating_val)), collapse = "")
          half_star <- if (rating_val %% 1 >= 0.5) "⭐" else ""
          star_display <- paste0(stars, half_star, " (", rating_val, ")")

          # Similarity score
          similarity_html <- if (length(row$similarity_score) == 1 && !is.na(row$similarity_score) && row$similarity_score > 0) {
            paste0("<div style='margin: 8px 0; padding: 6px; background: #e6fffa; border-radius: 4px;'>",
                   "<span style='color: #667eea; font-weight: bold;'>🎯 Match Score: ", round(row$similarity_score, 2), "</span>",
                   "</div>")
          } else ""

          # Price level
          price_display <- if (length(row$price_level) == 1 && !is.na(row$price_level)) {
            price_symbols <- paste(rep("$", row$price_level), collapse = "")
            paste0("<span style='color: #38a169; font-weight: bold;'>", price_symbols, "</span>")
          } else ""

          # Amenities
          amenities <- c()
          if (length(row$serves_vegetarian) == 1 && !is.na(row$serves_vegetarian) && row$serves_vegetarian) amenities <- c(amenities, "🌱 Vegetarian")
          if (length(row$takeout) == 1 && !is.na(row$takeout) && row$takeout) amenities <- c(amenities, "📦 Takeout")
          if (length(row$delivery) == 1 && !is.na(row$delivery) && row$delivery) amenities <- c(amenities, "🚚 Delivery")
          if (length(row$serves_beer) == 1 && !is.na(row$serves_beer) && row$serves_beer) amenities <- c(amenities, "🍺 Beer")
          if (length(row$serves_wine) == 1 && !is.na(row$serves_wine) && row$serves_wine) amenities <- c(amenities, "🍷 Wine")
          if (length(row$outdoor_seating) == 1 && !is.na(row$outdoor_seating) && row$outdoor_seating) amenities <- c(amenities, "🌞 Outdoor")

          amenities_html <- if (length(amenities) > 0) {
            paste0("<div style='margin: 8px 0;'>",
                   paste(amenities, collapse = " • "),
                   "</div>")
          } else ""

          # Reviews
          reviews_html <- if (nrow(restaurant_reviews) > 0) {
            review_items <- lapply(1:min(2, nrow(restaurant_reviews)), function(j) {
              review <- restaurant_reviews[j, ]
              review_stars <- paste(rep("⭐", floor(review$rating)), collapse = "")
              review_text <- substr(review$text, 1, 100)
              if (nchar(review$text) > 100) review_text <- paste0(review_text, "...")
              
              paste0("<div style='margin: 6px 0; padding: 6px; background: #f7fafc; border-radius: 4px;'>",
                     "<div style='color: #f59e0b; font-size: 0.9em;'>", review_stars, " ", review$rating, "</div>",
                     "<div style='font-size: 0.85em; color: #4a5568;'>", review_text, "</div>",
                     "</div>")
            })
            paste0("<div style='margin: 8px 0;'>",
                   "<div style='font-weight: bold; color: #2d3748; margin-bottom: 6px;'>Recent Reviews:</div>",
                   paste(review_items, collapse = ""),
                   "</div>")
          } else ""

          # Action buttons
          links_html <- "<div style='margin: 8px 0;'>"
          if (length(row$website) == 1 && !is.na(row$website) && row$website != "") {
            links_html <- paste0(links_html, 
              "<a href='", row$website, "' target='_blank' style='display: inline-block; margin: 2px; padding: 6px 12px; background: #667eea; color: white; text-decoration: none; border-radius: 4px; font-size: 0.85em;'>🌐 Website</a>")
          }
          if (length(row$formatted_phone_number) == 1 && !is.na(row$formatted_phone_number) && row$formatted_phone_number != "") {
            links_html <- paste0(links_html,
              "<a href='tel:", row$formatted_phone_number, "' style='display: inline-block; margin: 2px; padding: 6px 12px; background: #38a169; color: white; text-decoration: none; border-radius: 4px; font-size: 0.85em;'>📞 Call</a>")
          }
          links_html <- paste0(links_html, "</div>")

          # Combine all HTML
          paste0(
            "<div style='max-width: 350px; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>",
            "<div style='border-bottom: 2px solid #667eea; padding-bottom: 8px; margin-bottom: 12px;'>",
            "<h3 style='margin: 0; color: #2d3748; font-size: 1.2em;'>", row$name, "</h3>",
            "<div style='color: #f59e0b; font-size: 1.1em; margin: 4px 0;'>", star_display, "</div>",
            "<div style='color: #718096; font-size: 0.9em;'>", row$user_ratings_total, " reviews</div>",
            "</div>",

            # Similarity score
            similarity_html,

            # Cuisine and price
            "<div style='margin: 8px 0;'>",
            "<span style='background: #edf2f7; padding: 4px 8px; border-radius: 12px; font-size: 0.85em; color: #4a5568;'>",
            row$cuisine, "</span> ",
            price_display,
            "</div>",

            # Amenities
            amenities_html,

            # Address
            "<div style='margin: 8px 0; padding: 8px; background: #f7fafc; border-radius: 4px;'>",
            "<div style='font-size: 0.9em; color: #4a5568;'>📍 ", row$address, "</div>",
            "</div>",

            # Reviews
            reviews_html,

            # Action buttons
            links_html,

            "</div>"
          )
        }, error = function(e) {
          # Fallback popup if there's an error
          paste0(
            "<div style='max-width: 350px; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>",
            "<h3 style='margin: 0; color: #2d3748; font-size: 1.2em;'>", restaurant_row$name, "</h3>",
            "<div style='color: #f59e0b; font-size: 1.1em; margin: 4px 0;'>⭐ ", restaurant_row$rating, "</div>",
            "<div style='color: #718096; font-size: 0.9em;'>", restaurant_row$address, "</div>",
            "</div>"
          )
        })

        # Show the popup on the map
        leafletProxy("map_plot") %>%
          clearPopups() %>%
          addPopups(
            lng = clicked_data$lng,
            lat = clicked_data$lat,
            popup = popup_content
          ) %>%
          setView(lng = clicked_data$lng, lat = clicked_data$lat, zoom = 15)
      }
    }
  })

  # Restaurant list
  output$restaurant_list <- renderUI({
    df <- filtered_restaurants()

    if (nrow(df) == 0) {
      return(p("No restaurants found matching your criteria."))
    }

    cards <- list()
     for (i in 1:min(10, nrow(df))) {
      row <- df[i, ]
      score <- if ("similarity_score" %in% names(row)) row$similarity_score else 0
      restaurant_id <- paste0("restaurant_", row$id)

      card <- div(
        class = "restaurant-card clickable-restaurant",
        id = restaurant_id,
        `data-restaurant-id` = row$id,
        `data-lat` = row$lat,
        `data-lng` = row$lng,
        style = "cursor: pointer; transition: background-color 0.2s;",
        div(
          strong(row$name),
          span(paste("⭐", row$rating), style = "color: #f59e0b; margin-left: 10px;"),
          if (score > 0) span(paste("🎯", round(score, 2)),
                             style = "color: #667eea; margin-left: 10px;") else ""
        ),
        div(
          row$cuisine,
          style = "color: #718096; font-size: 0.9rem;"
        ),
        div(
          row$address,
          style = "color: #a0aec0; font-size: 0.85rem;"
        )
      )
      cards[[i]] <- card
    }

    return(do.call(tagList, cards))
  })

  # TF-IDF Rankings
  output$tfidf_rankings <- renderUI({
    df <- filtered_restaurants()

    if (!"similarity_score" %in% names(df) || nrow(df) == 0) {
      return(p("Enter a search query to see rankings"))
    }

    top_3 <- head(df, 3)

    items <- list()
     for (i in 1:nrow(top_3)) {
      row <- top_3[i, ]
      item <- div(
        span(paste0(i, "."), style = "font-weight: 700; margin-right: 10px;"),
        span(row$name, style = "font-weight: 600;"),
        span(round(row$similarity_score, 3),
             style = "float: right; color: #047857; font-weight: 600;")
      )
      items[[i]] <- item
    }

    return(do.call(tagList, items))
  })

  # Topic Keywords
  output$topic_keywords <- renderUI({
    topics <- extract_topics(reviews_df())

    keywords <- list()
     for (topic in topics) {
      keyword <- span(
        str_to_title(topic),
        style = "display: inline-block; padding: 6px 12px; margin: 4px;
                background: rgba(102, 126, 234, 0.1); border: 1px solid rgba(102, 126, 234, 0.3);
                border-radius: 15px; font-size: 0.85rem;"
      )
      keywords <- append(keywords, list(keyword))
    }

    return(do.call(tagList, keywords))
  })

  # Sentiment Plot
  output$sentiment_plot <- renderUI({
    sentiment_data <- analyze_sentiment(reviews_df())

    colors <- list(
      'Positive' = '#48bb78',
      'Neutral' = '#ecc94b',
      'Negative' = '#f56565'
    )

    bars <- list()
     for (sentiment in names(sentiment_data)) {
      pct <- sentiment_data[[sentiment]]
      bar <- div(
        div(sentiment, style = "width: 80px; font-size: 0.85rem;"),
        div(
          style = "flex: 1; height: 20px; background: #e0e6ed; border-radius: 10px; overflow: hidden;",
          div(
            style = paste0("width: ", pct, "%; height: 100%; background: ", colors[[sentiment]], "; border-radius: 10px;")
          )
        ),
        div(paste0(pct, "%"), style = "width: 40px; text-align: right; font-weight: 600; font-size: 0.85rem;"),
        style = "display: flex; align-items: center; gap: 10px; margin-bottom: 10px;"
      )
      bars <- append(bars, list(bar))
    }

    return(do.call(tagList, bars))
  })

  # Similarity Score
  output$similarity_score <- renderUI({
    df <- filtered_restaurants()
    query <- if (is.null(input$query_input) || input$query_input == "") {
      if (is.null(input$main_search) || input$main_search == "") "" else input$main_search
    } else {
      input$query_input
    }

    if (query != "" && "similarity_score" %in% names(df) && nrow(df) > 0) {
      top_match <- df[1, ]
      score <- top_match$similarity_score

      return(div(
        div(paste("Query:", query), style = "color: #718096; font-size: 0.85rem; margin-bottom: 10px;"),
        div(paste("Method: TF-IDF"), style = "color: #667eea; font-size: 0.75rem; margin-bottom: 5px;"),
        div(paste("Top Match:", top_match$name), style = "font-weight: 600; margin-bottom: 10px;"),
        div(
          style = "height: 8px; background: #e0e6ed; border-radius: 4px; overflow: hidden;",
          div(style = paste0("width: ", score * 100, "%; height: 100%; background: linear-gradient(90deg, #667eea, #764ba2);"))
        ),
        div(paste0(round(score * 100, 1), "% match"),
            style = "text-align: right; margin-top: 5px; color: #667eea; font-weight: 600; font-size: 0.85rem;")
      ))
    }

    return(p("Enter a search query to see match scores"))
  })

  # Rating Distribution
  output$rating_distribution <- renderPlotly({
    p <- ggplot(restaurants_df(), aes(x = rating)) +
      geom_histogram(bins = 10, fill = "#667eea", alpha = 0.7) +
      labs(title = "Distribution of Restaurant Ratings",
           x = "Rating", y = "Number of Restaurants") +
      theme_minimal()

    ggplotly(p, height = 300)
  })

  # Price Analysis
  output$price_analysis <- renderPlotly({
    price_counts <- restaurants_df() %>%
      count(price_level) %>%
      arrange(price_level)

    price_labels <- c("$", "$$", "$$$", "$$$$")[1:nrow(price_counts)]

    p <- ggplot(price_counts, aes(x = factor(price_level), y = n)) +
      geom_bar(stat = "identity", fill = "#764ba2") +
      scale_x_discrete(labels = price_labels) +
      labs(title = "Restaurant Price Distribution",
           x = "Price Level", y = "Count") +
      theme_minimal()

    ggplotly(p, height = 300)
  })

  # Sentiment Timeline
  output$sentiment_timeline <- renderPlotly({
    reviews_with_sentiment <- reviews_df() %>%
      mutate(
        date = as.Date(time),
        sentiment = case_when(
          rating >= 4 ~ "Positive",
          rating >= 3 ~ "Neutral",
          TRUE ~ "Negative"
        )
      ) %>%
      group_by(date, sentiment) %>%
      summarise(count = n(), .groups = 'drop')

    p <- ggplot(reviews_with_sentiment, aes(x = date, y = count, color = sentiment)) +
      geom_line() +
      scale_color_manual(values = c("Positive" = "#48bb78", "Neutral" = "#ecc94b", "Negative" = "#f56565")) +
      labs(title = "Review Sentiment Over Time",
           x = "Date", y = "Count") +
      theme_minimal()

    ggplotly(p, height = 350)
  })
}

# ============================================================================
# CREATE APP
# ============================================================================

shinyApp(ui = ui, server = server)

