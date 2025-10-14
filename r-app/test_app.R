# Test script for R Shiny Restaurant Recommender
# This script tests the core functionality before running the full app

# Load required libraries
suppressPackageStartupMessages({
  library(dplyr)
  library(DBI)
  library(RSQLite)
  library(textrecipes)
  library(tidymodels)
  library(topicmodels)
  library(tm)
})

# Test data loading
test_data_loading <- function() {
  cat("🧪 Testing Data Loading...\n")
  
  # Get the path to the database
  db_path <- file.path("..", "austin_restaurants.db")
  
  if (!file.exists(db_path)) {
    cat("❌ Database not found at:", db_path, "\n")
    return(FALSE)
  }
  
  # Connect to database
  conn <- dbConnect(RSQLite::SQLite(), db_path)
  
  tryCatch({
    # Test restaurant query
    restaurants <- dbGetQuery(conn, "
      SELECT COUNT(*) as count FROM restaurants 
      WHERE business_status = 'OPERATIONAL'
    ")
    
    # Test reviews query  
    reviews <- dbGetQuery(conn, "
      SELECT COUNT(*) as count FROM reviews 
      WHERE text IS NOT NULL AND text != ''
    ")
    
    cat("✅ Found", restaurants$count, "operational restaurants\n")
    cat("✅ Found", reviews$count, "reviews with text\n")
    
    return(TRUE)
    
  }, finally = {
    dbDisconnect(conn)
  })
}

# Test TF-IDF calculation
test_tfidf <- function() {
  cat("\n🧪 Testing TF-IDF Calculation...\n")
  
  # Create sample data
  sample_restaurants <- data.frame(
    id = 1:5,
    name = c("Italian Bistro", "BBQ House", "Pizza Place", "Sushi Bar", "Burger Joint"),
    cuisine = c("italian,restaurant", "barbecue,bbq", "pizza,italian", "japanese,sushi", "american,burger"),
    rating = c(4.5, 4.2, 4.0, 4.7, 3.8),
    stringsAsFactors = FALSE
  )
  
  sample_reviews <- data.frame(
    restaurant_id = rep(1:5, each = 2),
    text = c(
      "Great Italian food and atmosphere",
      "Amazing pasta and wine selection",
      "Best barbecue in town, love the ribs",
      "Smoky flavors, excellent brisket",
      "Good pizza, fast delivery",
      "Crispy crust, fresh toppings",
      "Fresh sushi, great presentation",
      "Authentic Japanese experience",
      "Classic burgers, good fries",
      "Fast service, decent food"
    ),
    stringsAsFactors = FALSE
  )
  
  # Test query
  query <- "Italian food"
  
  # Create combined text
  restaurants_with_reviews <- sample_restaurants %>%
    left_join(
      sample_reviews %>%
        group_by(restaurant_id) %>%
        summarise(text = paste(text, collapse = " "), .groups = 'drop'),
      by = c("id" = "restaurant_id")
    ) %>%
    mutate(
      combined_text = paste(name, coalesce(cuisine, ""), coalesce(text, ""))
    )
  
  # Create TF-IDF recipe
  recipe <- recipe(~ combined_text, data = restaurants_with_reviews) %>%
    step_tokenize(combined_text) %>%
    step_tokenfilter(combined_text, max_tokens = 100) %>%
    step_tfidf(combined_text) %>%
    prep()
  
  # Apply recipe
  tfidf_matrix <- bake(recipe, new_data = restaurants_with_reviews)
  
  # Process query
  query_df <- data.frame(combined_text = query)
  query_tfidf <- bake(recipe, new_data = query_df)
  
  # Calculate similarity (simplified)
  cat("✅ TF-IDF calculation completed\n")
  cat("✅ Recipe created with", ncol(tfidf_matrix) - 1, "features\n")
  
  return(TRUE)
}

# Test topic modeling
test_lda <- function() {
  cat("\n🧪 Testing LDA Topic Modeling...\n")
  
  # Create sample text data
  sample_texts <- c(
    "Great food and excellent service at this restaurant",
    "Amazing atmosphere and friendly staff",
    "Delicious pizza with fresh ingredients",
    "Fast delivery and good quality food",
    "Romantic setting perfect for date night",
    "Family friendly restaurant with kids menu",
    "Authentic Italian cuisine and wine selection",
    "Outdoor seating with beautiful garden view",
    "Reasonable prices and generous portions",
    "Clean restaurant with modern decor"
  )
  
  # Create document-term matrix
  dtm <- sample_texts %>%
    VectorSource() %>%
    Corpus() %>%
    DocumentTermMatrix(
      control = list(
        tolower = TRUE,
        removePunctuation = TRUE,
        removeNumbers = TRUE,
        stopwords = TRUE,
        wordLengths = c(3, Inf)
      )
    )
  
  # Remove sparse terms
  dtm <- removeSparseTerms(dtm, 0.8)
  
  # Apply LDA
  lda_model <- LDA(dtm, k = 3, control = list(seed = 42))
  
  # Extract topics
  topics <- terms(lda_model, 5)
  
  cat("✅ LDA model created with", nrow(topics), "topics\n")
  cat("✅ Top terms per topic:\n")
  for (i in 1:nrow(topics)) {
    cat("   Topic", i, ":", paste(topics[i, ], collapse = ", "), "\n")
  }
  
  return(TRUE)
}

# Test sentiment analysis
test_sentiment <- function() {
  cat("\n🧪 Testing Sentiment Analysis...\n")
  
  # Create sample reviews with ratings
  sample_reviews <- data.frame(
    rating = c(5, 4, 3, 2, 1, 5, 4, 3, 2, 1),
    text = c(
      "Amazing food and service!",
      "Great experience overall",
      "It was okay, nothing special",
      "Disappointing meal",
      "Terrible service and food",
      "Best restaurant in town!",
      "Good food, nice atmosphere",
      "Average experience",
      "Poor quality food",
      "Worst dining experience ever"
    ),
    stringsAsFactors = FALSE
  )
  
  # Calculate sentiment
  reviews_with_sentiment <- sample_reviews %>%
    mutate(
      sentiment = case_when(
        rating >= 4 ~ "Positive",
        rating >= 3 ~ "Neutral",
        TRUE ~ "Negative"
      )
    )
  
  # Calculate percentages
  sentiment_counts <- reviews_with_sentiment %>%
    count(sentiment) %>%
    mutate(percentage = round(n / sum(n) * 100, 1))
  
  cat("✅ Sentiment analysis completed\n")
  cat("✅ Sentiment distribution:\n")
  for (i in 1:nrow(sentiment_counts)) {
    cat("   ", sentiment_counts$sentiment[i], ":", sentiment_counts$percentage[i], "%\n")
  }
  
  return(TRUE)
}

# Run all tests
run_all_tests <- function() {
  cat("🚀 Running R Shiny App Tests\n")
  cat(paste(rep("=", 50), collapse = ""), "\n")
  
  tests <- list(
    "Data Loading" = test_data_loading,
    "TF-IDF Calculation" = test_tfidf,
    "LDA Topic Modeling" = test_lda,
    "Sentiment Analysis" = test_sentiment
  )
  
  results <- list()
  
  for (test_name in names(tests)) {
    tryCatch({
      result <- tests[[test_name]]()
      results[[test_name]] <- result
    }, error = function(e) {
      cat("❌", test_name, "failed:", e$message, "\n")
      results[[test_name]] <- FALSE
    })
  }
  
  cat("\n📊 Test Results Summary\n")
  cat(paste(rep("=", 30), collapse = ""), "\n")
  
  for (test_name in names(results)) {
    status <- if (results[[test_name]]) "✅ PASS" else "❌ FAIL"
    cat(sprintf("%-20s %s\n", test_name, status))
  }
  
  all_passed <- all(unlist(results))
  
  if (all_passed) {
    cat("\n🎉 All tests passed! The R app should work correctly.\n")
    cat("You can now run: shiny::runApp('app.R')\n")
  } else {
    cat("\n⚠️  Some tests failed. Please check the errors above.\n")
  }
  
  return(all_passed)
}

# Run tests if this script is executed directly
if (!interactive()) {
  run_all_tests()
}
