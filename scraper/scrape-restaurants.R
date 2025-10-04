library(googleway)
library(tidyverse)
library(glue)


# Preface -----------------------------------------------------------------

# Note - I wrote the script manually, but it became a bit messy after running through everything interactively
# below is AI's version of minimally documenting the process and adding a bit of commentary

# Configuration -----------------------------------------------------------

api_key <- Sys.getenv("google_places_api_key")
choose_opts <- c("restaurant", "cafe", "bar")
austin_coords_global <- c(30.286071, -97.739352)

# Grid Creation -----------------------------------------------------------

create_dense_grid <- function(center_lat, center_lng, radius_miles = 10,
                              search_radius_miles = 0.5) {
  # Calculate degrees per mile for latitude and longitude
  miles_per_degree_lat <- 69
  miles_per_degree_lng <- 69 * cos(center_lat * pi / 180)

  # Convert radius from miles to degrees
  total_radius_degrees_lat <- radius_miles / miles_per_degree_lat
  total_radius_degrees_lng <- radius_miles / miles_per_degree_lng

  search_radius_degrees_lat <- search_radius_miles / miles_per_degree_lat
  search_radius_degrees_lng <- search_radius_miles / miles_per_degree_lng

  # Create grid with 1.5x spacing for overlap
  spacing_lat <- search_radius_degrees_lat * 1.5
  spacing_lng <- search_radius_degrees_lng * 1.5

  lat_seq <- seq(
    center_lat - total_radius_degrees_lat,
    center_lat + total_radius_degrees_lat,
    by = spacing_lat
  )
  lng_seq <- seq(
    center_lng - total_radius_degrees_lng,
    center_lng + total_radius_degrees_lng,
    by = spacing_lng
  )

  # Generate grid and filter to circular area
  grid <- expand_grid(lat = lat_seq, lng = lng_seq) %>%
    mutate(
      grid_id = row_number(),
      distance_from_center = sqrt((lat - center_lat)^2 + (lng - center_lng)^2)
    ) %>%
    filter(distance_from_center <= total_radius_degrees_lat * 1.1)

  # Print grid summary
  cat(glue("\nGrid Configuration:\n"))
  cat(glue("  Total coverage: {radius_miles} miles radius\n"))
  cat(glue("  Search radius per point: {search_radius_miles} miles\n"))
  cat(glue("  Grid points: {nrow(grid)}\n"))
  cat(glue("  Estimated API calls: {nrow(grid) * 3} (max)\n\n"))

  return(grid)
}

# Data Extraction ---------------------------------------------------------

get_google_res_raw <- function(google_res) {
  # Extract location data
  location_res <- google_res$results$geometry$location

  # Get pagination token
  next_pg <- google_res$next_page_token

  # Flatten place types into comma-separated string
  place_type <- google_res$results$types %>%
    map_dfr(~ {
      tibble(place_tags = unlist(.x) %>% paste(collapse = ","))
    })

  # Combine all data
  new_res <- google_res$results %>%
    as_tibble() %>%
    print() %>%
    select(-where(is_list)) %>%
    select(
      id = reference,
      name,
      business_status,
      price_level,
      rating,
      user_ratings_total,
      address = vicinity
    ) %>%
    bind_cols(location_res) %>%
    bind_cols(place_type) %>%
    mutate(next_pg = next_pg)

  return(new_res)
}

# Wrap in safely() to handle errors gracefully
get_google_res <- safely(get_google_res_raw)

# Grid Setup --------------------------------------------------------------

austin_grid <- create_dense_grid(
  austin_coords_global[1],
  austin_coords_global[2]
)

# Main Scraping Loop ------------------------------------------------------

if (FALSE) {
  austin_grid %>%
    split(.$grid_id) %>%
    iwalk(~ {
      # Set coordinates for this grid point
      austin_coords <- c(.x$lat, .x$lng)
      grid_id <- .y

      # Paginate through up to 3 pages of results
      walk2(1:3, grid_id, ~ {
        print(.x)

        if (.x == 1) {
          # First page: initial search
          res_ret <- google_places(
            location = austin_coords,
            radius = 1609 * 0.5,
            place_type = choose_opts[1],
            key = api_key,
            simplify = TRUE
          )
          this_pg <<- get_google_res(res_ret)$result
          print(unique(this_pg$next_pg))
        } else {
          # Subsequent pages: use pagination token
          res_ret <- google_places(
            key = api_key,
            location = austin_coords,
            radius = 1609 * 0.5,
            place_type = choose_opts[1],
            page_token = unique(this_pg$next_pg)
          )
          this_pg <<- get_google_res(res_ret)$result
        }

        # Save results if valid
        if (is.data.frame(this_pg)) {
          write_csv(this_pg, glue("raw-res/raw-res__{.y}__{.x}.csv"))
        }

        # Respect API rate limits
        Sys.sleep(3)
      })
    })
}

# Combine Results ---------------------------------------------------------

test_output <- list.files("raw-res", full.names = TRUE) %>%
  imap_dfr(~ read_csv(.), .id = "grid")

# Deduplicate and consolidate place tags
test_output %>%
  group_by(id) %>%
  mutate(
    place_tags = place_tags %>%
      str_split(",") %>%
      unlist() %>%
      unique() %>%
      paste(collapse = ",")
  ) %>%
  distinct(
    id, name, business_status, price_level, rating,
    user_ratings_total, address, lat, lng, place_tags
  )
# %>% write_csv('data/austin_restaurants.csv')

# Place Details Scraping --------------------------------------------------

restaurant_details <- read_csv("data/austin_restaurants.csv")

get_restaurant_details_raw <- function(place_id) {
  # Fetch detailed place information
  pl_details <- googleway::google_place_details(
    place_id = place_id,
    key = api_key
  )

  # Extract scalar fields
  place_details <- pl_details$result[lapply(pl_details$result, length) == 1]
  place_details$open_times <- pl_details$result$current_opening_hours$weekday_text %>%
    paste(collapse = "||")
  place_details$summary <- pl_details$result$editorial_summary$overview
  place_details <- place_details %>%
    as_tibble() %>%
    mutate(id = place_id)

  # Extract photos
  place_photos <- pl_details$result$photos %>%
    as_tibble() %>%
    unnest(html_attributions) %>%
    mutate(id = place_id)

  # Extract reviews
  place_reviews <- pl_details$result$reviews %>%
    as_tibble() %>%
    mutate(id = place_id)

  # Save to individual files
  write_csv(place_photos, glue("raw-data/photos/{place_id}.csv"))
  write_csv(place_reviews, glue("raw-data/reviews/{place_id}.csv"))
  write_csv(place_details, glue("raw-data/place_details/{place_id}.csv"))
}

# Wrap in safely() to handle errors
get_restaurant_details <- safely(get_restaurant_details_raw)

# Scrape details for all restaurants
if (FALSE) {
  restaurant_details %>%
    distinct(id) %>%
    pull() %>%
    walk(~ get_restaurant_details(.))
}

# Fine-Grained Grid Search for Dense Areas -------------------------------

# Identify grid points that hit the 60-result limit
small_austin_grid <- create_dense_grid(
  austin_coords_global[1],
  austin_coords_global[2]
) %>%
  filter(grid_id %in% (
    test_output %>%
      rowwise() %>%
      mutate(grid = str_split(grid, "__") %>% unlist() %>% .[[2]]) %>%
      distinct(grid, id) %>%
      group_by(grid) %>%
      tally(sort = TRUE) %>%
      filter(n == 60) %>%
      pull(grid)
  )) %>%
  # Create sub-grid for each saturated grid point
  mutate(new_grid = map2(
    lat, lng,
    ~ create_dense_grid(.x, .y, radius_miles = 0.5, search_radius_miles = 0.2)
  )) %>%
  select(old_grid = grid_id, new_grid) %>%
  unnest(new_grid) %>%
  mutate(grid_id = paste0(old_grid, grid_id)) %>%
  select(lat, lng, grid_id, distance_from_center)

# Scrape fine-grained grid
if (FALSE) {
  small_austin_grid %>%
    split(.$grid_id) %>%
    iwalk(~ {
      austin_coords <- c(.x$lat, .x$lng)
      grid_id <- .y

      walk2(1:3, grid_id, ~ {
        print(.x)

        if (.x == 1) {
          res_ret <- google_places(
            location = austin_coords,
            radius = 1609 * 0.2,
            place_type = choose_opts[1],
            key = api_key,
            simplify = TRUE
          )
          this_pg <<- get_google_res(res_ret)$result
          print(unique(this_pg$next_pg))
        } else {
          res_ret <- google_places(
            key = api_key,
            location = austin_coords,
            radius = 1609 * 0.2,
            place_type = choose_opts[1],
            page_token = unique(this_pg$next_pg)
          )
          this_pg <<- get_google_res(res_ret)$result
        }

        if (is.data.frame(this_pg)) {
          write_csv(this_pg, glue("raw-res/raw-res__{.y}__{.x}.csv"))
        }
      })
    })
}

# Consolidate Data --------------------------------------------------------

# Combine all raw data files into clean CSVs
c("photos", "reviews", "place_details") %>%
  walk(~ {
    list.files(glue("raw-data/{.x}"), pattern = ".csv", full.names = TRUE) %>%
      map_dfr(~ read_csv(., col_types = "c")) %>%
      write_csv(glue("data/{.x}.csv"))
  })

# Verify final data
list.files("data", full.names = TRUE) %>%
  map(~ read_csv(.))



# Create Sql Lite Database ------------------------------------------------

library(RSQLite)

con <- dbConnect(RSQLite::SQLite(), "austin_restaurants.db")

c("photos","reviews","place_details","restaurants") %>%
  setNames(.,.) %>%
  imap(~{
    df <- read_csv(glue::glue("data/{.x}.csv"))
    dbWriteTable(con,.x,df)
  })


dbExecute(con, "CREATE INDEX IF NOT EXISTS idx_restaurants_id ON restaurants(id)")
dbExecute(con, "CREATE INDEX IF NOT EXISTS idx_details_id ON place_details(id)")
dbExecute(con, "CREATE INDEX IF NOT EXISTS idx_reviews_id ON reviews(id)")
dbExecute(con, "CREATE INDEX IF NOT EXISTS idx_photos_id ON photos(id)")

dbListTables(con)

