# Minimal RestaurantJi Scraper in R using chromote

library(chromote)
library(tidyverse)
library(rvest)
library(jsonlite)

# Load progress from file
load_progress <- function(progress_file) {
  if (file.exists(progress_file)) {
    tryCatch({
      progress <- fromJSON(progress_file)
      return(progress$scraped)
    }, error = function(e) {
      return(c())
    })
  }
  return(c())
}

# Save progress to file
save_progress <- function(restaurant_query, scraped_restaurants, progress_file) {
  scraped_restaurants <- c(scraped_restaurants, restaurant_query)
  progress <- list(
    scraped = scraped_restaurants,
    last_update = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
  )
  write_json(progress, progress_file)
  return(scraped_restaurants)
}

# Calculate string similarity score
calculate_match_score <- function(query, name) {
  if (!require(stringdist, quietly = TRUE)) {
    install.packages("stringdist")
    library(stringdist)
  }
  stringdist::stringsim(tolower(query), tolower(name), method = "cosine")
}

# Check if restaurant already scraped
is_already_scraped <- function(restaurant_query, scraped_restaurants) {
  tolower(restaurant_query) %in% tolower(scraped_restaurants)
}

# Save data to CSV
save_data <- function(results, restaurant_query, output_file) {
  if (nrow(results) == 0) return()

  if (file.exists(output_file)) {
    write_csv(results, output_file, append = TRUE)
    cat("   💾 Appended", nrow(results), "rows to", output_file, "\n")
  } else {
    write_csv(results, output_file)
    cat("   💾 Created", output_file, "with", nrow(results), "rows\n")
  }

  # Create backup
  dir.create("backups", showWarnings = FALSE)
  timestamp <- format(Sys.time(), "%Y%m%d_%H%M%S")
  backup_file <- sprintf("backups/backup_%s_%s.csv", timestamp, gsub(" ", "_", restaurant_query))
  write_csv(results, backup_file)
  cat("   💾 Backup saved:", backup_file, "\n")
}

# Scrape single restaurant
scrape_restaurant <- function(query, b, location = "Austin, TX", min_match_score = 0.6) {
  cat("\n", strrep("=", 70), "\n")
  cat("🔍 Processing:", query, "\n")
  cat(strrep("=", 70), "\n")

  tryCatch({
    # Search for restaurant
    search_url <- sprintf(
      "https://www.restaurantji.com/search/?query=%s&place=%s",
      gsub(" ", "+", query),
      gsub(" ", "+", location)
    )
    cat("🔍 Searching:", search_url, "\n")

    b$navigate(search_url)
    Sys.sleep(3)

    # Parse search results
    html <- b$get_content()
    page <- read_html(html)

    links <- page %>%
      html_elements("a[href]") %>%
      map_df(function(link) {
        href <- html_attr(link, "href")
        name <- html_text(link)

        if (!is.na(href) && stringr::str_count(href, "/") == 4 &&
            stringr::str_starts(href, "/") && stringr::str_ends(href, "/") &&
            nchar(name) > 0) {
          tibble(
            name = name,
            url = paste0("https://www.restaurantji.com", href),
            score = calculate_match_score(query, name)
          )
        } else {
          NULL
        }
      })

    if (nrow(links) == 0) {
      cat("❌ No restaurants found\n")
      return(tibble())
    }

    # Get best match
    best_match <- links %>%
      slice_max(score, n = 1) %>%
      slice(1)

    cat("✓ Best match:", best_match$name, "- Score:", round(best_match$score, 2), "\n")

    if (best_match$score < min_match_score) {
      cat("⚠️  Low match score\n")
      return(tibble())
    }

    # Get comments page
    comments_url <- paste0(best_match$url, "comments/")
    cat("📝 Fetching comments:", comments_url, "\n")

    b$navigate(comments_url)
    Sys.sleep(3)

    # Click load more button
    for (attempt in 1:3) {
      tryCatch({
        cat("Attempt", attempt, ": Clicking load more...\n")
        b$invoke(
          "Runtime.evaluate",
          list(expression = "document.querySelector('a.btn.more_comments')?.click()")
        )
        Sys.sleep(1)
      }, error = function(e) {
        cat("  Load more failed\n")
      })
    }

    # Extract comments
    html <- b$get_content()
    page <- read_html(html)
    comment_elements <- page %>% html_elements(".comment-content")

    cat("trying to parse results\n")

    results <- map_df(comment_elements, function(elem) {
      comment_html <- as.character(elem)
      comment_text <- elem %>% html_text(trim = TRUE)

      if (nchar(comment_text) > 0) {
        tibble(
          input_query = query,
          restaurant_name = best_match$name,
          restaurant_url = best_match$url,
          match_score = best_match$score,
          comment_html = comment_html,
          comment_text = comment_text,
          scraped_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S")
        )
      } else {
        NULL
      }
    })

    cat("✓ Found", nrow(results), "comments\n")
    return(results)

  }, error = function(e) {
    cat("❌ Error:", e$message, "\n")
    return(tibble())
  })
}

# Main scraper function
scrape_multiple <- function(restaurants, location = "Austin, TX",
                            min_match_score = 0.6, delay = 3) {
  cat("\n", strrep("#", 70), "\n")
  cat("🍽️  FAIL-SAFE SCRAPER\n")
  cat(strrep("#", 70), "\n\n")

  output_file <- "restaurant_comments.csv"
  progress_file <- "scraper_progress.json"

  # Load progress
  scraped_restaurants <- load_progress(progress_file)
  cat("📂 Loaded progress:", length(scraped_restaurants), "restaurants already scraped\n\n")

  # Start browser
  b <- ChromoteSession$new()

  successful <- 0
  failed <- 0
  skipped <- 0

  for (i in seq_along(restaurants)) {
    restaurant <- restaurants[i]
    start_time <- Sys.time()

    cat("\n", strrep("=", 70), "\n")
    cat("Restaurant", i, "/", length(restaurants), "\n")
    cat(strrep("=", 70), "\n")

    if (is_already_scraped(restaurant, scraped_restaurants)) {
      cat("✅ Already scraped! Skipping\n")
      skipped <- skipped + 1
      next
    }

    tryCatch({
      results <- scrape_restaurant(restaurant, b, location, min_match_score)

      elapsed <- as.numeric(difftime(Sys.time(), start_time, units = "secs"))
      cat("⏱️  Took", round(elapsed, 1), "seconds\n")

      if (nrow(results) > 0) {
        save_data(results, restaurant, output_file)
        scraped_restaurants <- save_progress(restaurant, scraped_restaurants, progress_file)
        cat("✅ Data saved successfully\n")
        successful <- successful + 1
      } else {
        failed <- failed + 1
      }
    }, error = function(e) {
      failed <<- failed + 1
      cat("❌ Fatal error:", e$message, "\n")
    })

    if (i < length(restaurants)) {
      cat("\n⏳ Waiting", delay, "seconds before next...\n")
      Sys.sleep(delay)
    }
  }

  b$close()

  # Summary
  cat("\n", strrep("=", 70), "\n")
  cat("FINAL SUMMARY\n")
  cat(strrep("=", 70), "\n")
  cat("✅ Successful:", successful, "\n")
  cat("❌ Failed:", failed, "\n")
  cat("⭐️  Skipped:", skipped, "\n")

  if (file.exists(output_file)) {
    df <- read_csv(output_file, show_col_types = FALSE)
    cat("\n📊 Total comments:", nrow(df), "\n")
    cat("📊 Unique restaurants:", n_distinct(df$restaurant_name), "\n")
    cat("\n💾 All data saved to:", output_file, "\n")
  }

  cat(strrep("=", 70), "\n")
}

# Run scraper
restaurants <- read_csv("r-scraper/extra_rest.csv", show_col_types = FALSE) %>% pull(name)
scrape_multiple(restaurants, location = "Austin, TX", min_match_score = 0.6, delay = 3)
