# RestaurantJi Scraper with Progress Tracking

library(chromote)
library(tidyverse)
library(rvest)
library(jsonlite)
library(glue)
# setwd("r-scraper")
# Load progress from JSON
load_progress <- function(progress_file = "scraper_progress.json") {
  if (file.exists(progress_file)) {
    tryCatch({
      progress <- fromJSON(progress_file)
      cat("📂 Loaded progress:", length(progress$scraped), "restaurants already scraped\n")
      return(progress$scraped)
    }, error = function(e) {
      cat("⚠️ Could not load progress file\n")
      return(c())
    })
  }
  return(c())
}

# Save progress to JSON
save_progress <- function(restaurant_id, scraped_ids, progress_file = "scraper_progress.json") {
  scraped_ids <- c(scraped_ids, restaurant_id)
  progress <- list(
    scraped = scraped_ids,
    last_update = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
  )
  write_json(progress, progress_file)
  return(scraped_ids)
}

# Check if already scraped
is_already_scraped <- function(restaurant_id, scraped_ids) {
  restaurant_id %in% scraped_ids
}

# Save data with backup
save_data <- function(results, restaurant_name, output_file = "restaurant_comments.csv") {
  if (nrow(results) == 0) return()

  if (file.exists(output_file)) {
    write_csv(results, output_file, append = TRUE)
    cat("   💾 Appended", nrow(results), "rows\n")
  } else {
    write_csv(results, output_file)
    cat("   💾 Created file with", nrow(results), "rows\n")
  }

  # Create backup
  dir.create("backups", showWarnings = FALSE)
  timestamp <- format(Sys.time(), "%Y%m%d_%H%M%S")
  backup_file <- sprintf("backups/backup_%s_%s.csv", timestamp, gsub(" ", "_", restaurant_name))
  write_csv(results, backup_file)
  cat("   💾 Backup saved\n")
}

# Get comments from restaurant page
get_comments <- function(name, id, url, restaurant_name, match_score) {
  b <- ChromoteSession$new()
  tryCatch({
    page <- glue("{url}comments/")
    cat("📝 Fetching:", page, "\n")
    b$go_to(page)
    Sys.sleep(2)

    # Click load more buttons
    for(i in 1:5) {
      cat("  Attempt", i, ": Clicking load more...\n")
      tryCatch({
        b$Runtime$evaluate("document.querySelector('a.btn.more_comments').click()")
        Sys.sleep(1.5)
      }, error = function(e) {
        cat("    Load more failed\n")
      })
    }

    # Get HTML
    html_content <- b$Runtime$evaluate("document.documentElement.outerHTML")$result$value

    # Parse comments
    new_data <- read_html(html_content) %>%
      html_nodes(".comment-content") %>%
      map_dfr(~{
        tibble(
          comment_html = as.character(.x) %>% str_squish(),
          comment_text = html_text(.x, trim = TRUE) %>% str_squish()
        )
      })

    cat("✓ Found", nrow(new_data), "comments\n")

    # Add metadata
    new_data %>%
      mutate(
        name = name,
        id = id,
        restaurant_name = restaurant_name,
        match_score = match_score,
        scraped_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
      )

  }, error = function(e) {
    cat("❌ Error:", e$message, "\n")
    tibble()
  }, finally = {
    b$close()
  })
}

get_comments_safe <- safely(get_comments)

# Main scraper with progress tracking
scrape_restaurants <- function(restaurants_df,
                               output_file = "restaurant_comments.csv",
                               progress_file = "scraper_progress.json",
                               delay = 3) {

  cat("\n", strrep("#", 70), "\n")
  cat("🍽️  SCRAPER WITH PROGRESS TRACKING\n")
  cat(strrep("#", 70), "\n")
  cat("Total restaurants:", nrow(restaurants_df), "\n")

  # Load progress
  scraped_ids <- load_progress(progress_file)
  cat("To scrape:", nrow(restaurants_df) - length(scraped_ids), "\n")
  cat(strrep("#", 70), "\n\n")

  successful <- 0
  failed <- 0
  skipped <- 0

  for (row in 1:nrow(restaurants_df)) {
    restaurant <- restaurants_df[row, ]
    restaurant_id <- restaurant$id
    restaurant_name <- restaurant$restaurant_name

    start_time <- Sys.time()

    cat("\n", strrep("=", 70), "\n")
    cat("Restaurant", row, "/", nrow(restaurants_df), "\n")
    cat("🔍 Processing:", restaurant_name, "\n")
    cat(strrep("=", 70), "\n")

    # Check if already scraped
    if (is_already_scraped(restaurant_id, scraped_ids)) {
      cat("✅ Already scraped! Skipping\n")
      skipped <- skipped + 1
      next
    }

    # Scrape
    result <- get_comments_safe(
      restaurant$name,
      restaurant$id,
      restaurant$restaurant_url,
      restaurant$restaurant_name,
      restaurant$match_score
    )

    elapsed <- as.numeric(difftime(Sys.time(), start_time, units = "secs"))
    cat("⏱️  Took", round(elapsed, 1), "seconds\n")

    # Save if successful
    if (!is.null(result$result) && nrow(result$result) > 0) {
      save_data(result$result, restaurant_name, output_file)
      scraped_ids <- save_progress(restaurant_id, scraped_ids, progress_file)
      cat("✅ Data saved successfully\n")
      successful <- successful + 1
    } else {
      if (is.null(result$error)) {
        failed <- failed + 1
      } else {
        cat("❌ Error:", result$error$message, "\n")
        failed <- failed + 1
      }
    }

    # Wait between requests
    if (row < nrow(restaurants_df)) {
      cat("\n⏳ Waiting", delay, "seconds before next...\n")
      Sys.sleep(delay)
    }
  }

  # Summary
  cat("\n", strrep("=", 70), "\n")
  cat("FINAL SUMMARY\n")
  cat(strrep("=", 70), "\n")
  cat("✅ Successful:", successful, "\n")
  cat("❌ Failed:", failed, "\n")
  cat("⭐️  Skipped (already done):", skipped, "\n")

  if (file.exists(output_file)) {
    df <- read_csv(output_file, show_col_types = FALSE)
    cat("\n📊 Total comments:", nrow(df), "\n")
    cat("📊 Unique restaurants:", n_distinct(df$restaurant_name), "\n")
    cat("\n💾 All data saved to:", output_file, "\n")
  }

  cat(strrep("=", 70), "\n")
  cat("\n💡 TIP: If interrupted, just run again! It will skip already-scraped restaurants.\n\n")
}

# Usage:
restaurants <- read_csv('new_rest_scrape.csv')
scrape_restaurants(restaurants, delay = 3)
