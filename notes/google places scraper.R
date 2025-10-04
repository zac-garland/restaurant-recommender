library(googleway)
library(tidyverse)

# NOTE: This is the original messy scraper

api_key <- Sys.getenv("google_places_api_key")

choose_opts <- c("restaurant", "cafe", "bar")


create_dense_grid <- function(center_lat, center_lng, radius_miles = 10,
                              search_radius_miles = 0.5) {
  miles_per_degree_lat <- 69
  miles_per_degree_lng <- 69 * cos(center_lat * pi / 180)

  total_radius_degrees_lat <- radius_miles / miles_per_degree_lat
  total_radius_degrees_lng <- radius_miles / miles_per_degree_lng

  search_radius_degrees_lat <- search_radius_miles / miles_per_degree_lat
  search_radius_degrees_lng <- search_radius_miles / miles_per_degree_lng

  spacing_lat <- search_radius_degrees_lat * 1.5
  spacing_lng <- search_radius_degrees_lng * 1.5

  lat_seq <- seq(center_lat - total_radius_degrees_lat,
    center_lat + total_radius_degrees_lat,
    by = spacing_lat
  )
  lng_seq <- seq(center_lng - total_radius_degrees_lng,
    center_lng + total_radius_degrees_lng,
    by = spacing_lng
  )

  grid <- expand_grid(lat = lat_seq, lng = lng_seq) %>%
    mutate(
      grid_id = row_number(),
      distance_from_center = sqrt((lat - center_lat)^2 + (lng - center_lng)^2)
    ) %>%
    filter(distance_from_center <= total_radius_degrees_lat * 1.1)

  cat(glue("\nGrid Configuration:\n"))
  cat(glue("  Total coverage: {radius_miles} miles radius\n"))
  cat(glue("  Search radius per point: {search_radius_miles} miles\n"))
  cat(glue("  Grid points: {nrow(grid)}\n"))
  cat(glue("  Estimated API calls: {nrow(grid) * 3} (max)\n\n"))

  return(grid)
}


get_google_res_raw <- function(google_res) {
  location_res <- google_res$results$geometry$location

  next_pg <- google_res$next_page_token

  place_type <- google_res$results$types %>% map_dfr(~ {
    tibble(place_tags = unlist(.x) %>% paste(collapse = ","))
  })

  new_res <- google_res$results %>%
    as_tibble() %>%
    print() %>%
    select(-where(is_list)) %>%
    select(id = reference, name, business_status, price_level, rating, user_ratings_total, address = vicinity) %>%
    bind_cols(
      location_res
    ) %>%
    bind_cols(place_type) %>%
    mutate(
      next_pg = next_pg
    )

  new_res
}

get_google_res <- safely(get_google_res_raw)

austin_coords_global <- c(30.286071, -97.739352)

austin_grid <- create_dense_grid(austin_coords_global[1], austin_coords_global[2])


if (FALSE) {
  austin_grid %>%
    # sample_n(5) %>%
    split(.$grid_id) %>%
    iwalk(~ {
      austin_coords <- c(.x$lat, .x$lng)
      grid_id <- .y
      walk2(1:3, grid_id, ~ {
        print(.x)
        if (.x == 1) {
          res_ret <- google_places(
            location = austin_coords, radius = 1609 * 0.5, place_type = choose_opts[1],
            key = api_key, simplify = TRUE
          )
          this_pg <<- get_google_res(res_ret)$result
          print(unique(this_pg$next_pg))
        } else {
          res_ret <- google_places(
            key = api_key,
            location = austin_coords, radius = 1609 * 0.5,
            place_type = choose_opts[1],
            page_token = unique(this_pg$next_pg)
          )
          this_pg <<- get_google_res(res_ret)$result
        }

        if (is.data.frame(this_pg)) {
          write_csv(this_pg, glue::glue("raw-res/raw-res__{.y}__{.x}.csv"))
        }


        Sys.sleep(3)
      })
    })
}



test_output <- list.files("raw-res",full.names = TRUE) %>% imap_dfr(~read_csv(.),.id = "grid")

# usethis::use_directory("data")

test_output %>%
  group_by(id) %>%
  mutate(
    place_tags = place_tags %>% str_split(",") %>% unlist() %>% unique() %>% paste(collapse = ",")
  ) %>%
  distinct(id,name,business_status,price_level,rating,user_ratings_total,address,lat,lng,place_tags) %>%
#   write_csv('data/austin_restaurants.csv')



restaurant_details <- read_csv("data/austin_restaurants.csv")

restaurant_details %>%
  group_by(grid) %>%
  tally(sort = TRUE)

# restaurant_details %>%
#   distinct(id,name)

get_restaurant_details_raw <- function(place_id) {
  pl_details <- googleway::google_place_details(place_id = place_id, key = api_key)


  place_details <- pl_details$result[lapply(pl_details$result, length) == 1]
  place_details$open_times <- pl_details$result$current_opening_hours$weekday_text %>% paste(collapse = "||")
  place_details$summary <- pl_details$result$editorial_summary$overview
  place_details <- place_details %>%
    as_tibble() %>%
    mutate(id = place_id)
  place_photos <- pl_details$result$photos %>%
    as_tibble() %>%
    unnest(html_attributions) %>%
    mutate(id = place_id)
  place_reviews <- pl_details$result$reviews %>%
    as_tibble() %>%
    mutate(id = place_id)

  write_csv(place_photos, glue::glue("raw-data/photos/{place_id}.csv"))
  write_csv(place_reviews, glue::glue("raw-data/reviews/{place_id}.csv"))
  write_csv(place_details, glue::glue("raw-data/place_details/{place_id}.csv"))
}



get_restaurant_details <- safely(get_restaurant_details_raw)

restaurant_details %>%
  mutate(score = rating * log(user_ratings_total)) %>%
  arrange(desc(score))


restaurant_details %>%
  distinct(id) %>%
  pull() %>%
  walk(~ get_restaurant_details(.))
# rm(list = ls())



# smaller grid search fill in ---------------------------------------------


small_austin_grid <- create_dense_grid(austin_coords_global[1], austin_coords_global[2]) %>%
  filter(grid_id %in% (test_output %>% rowwise() %>% mutate(grid = str_split(grid, "__") %>% unlist() %>% .[[2]]) %>%
    distinct(grid, id) %>% group_by(grid) %>% tally(sort = TRUE) %>% filter(n == 60) %>% pull(grid))) %>%
  mutate(new_grid = map2(lat, lng, ~ create_dense_grid(.x, .y, radius_miles = 0.5, search_radius_miles = 0.2))) %>%
  select(old_grid = grid_id, new_grid) %>%
  unnest(new_grid) %>%
  mutate(grid_id = paste0(old_grid,grid_id)) %>%
  select(lat,lng,grid_id,distance_from_center)

small_austin_grid


if (FALSE) {
  small_austin_grid %>%
    # sample_n(5) %>%
    split(.$grid_id) %>%
    iwalk(~ {
      austin_coords <- c(.x$lat, .x$lng)
      grid_id <- .y
      walk2(1:3, grid_id, ~ {
        print(.x)
        if (.x == 1) {
          res_ret <- google_places(
            location = austin_coords, radius = 1609 * 0.2, place_type = choose_opts[1],
            key = api_key, simplify = TRUE
          )
          this_pg <<- get_google_res(res_ret)$result
          print(unique(this_pg$next_pg))
        } else {
          res_ret <- google_places(
            key = api_key,
            location = austin_coords, radius = 1609 * 0.2,
            place_type = choose_opts[1],
            page_token = unique(this_pg$next_pg)
          )
          this_pg <<- get_google_res(res_ret)$result
        }

        if (is.data.frame(this_pg)) {
          write_csv(this_pg, glue::glue("raw-res/raw-res__{.y}__{.x}.csv"))
        }

      })
    })
}



c("photos","reviews","place_details") %>%
walk(~{
  list.files(glue::glue("raw-data/{.x}"),pattern = ".csv",full.names = TRUE) %>%
    map_dfr(~read_csv(.,col_types = "c")) %>%
    # mutate_all(parse_guess) %>%
    write_csv(glue::glue('data/{.x}.csv'))
})


list.files("data",full.names = TRUE) %>%
  map(~read_csv(.))


# usethis::use_directory("raw-data/photos")
# usethis::use_directory("raw-data/reviews")
# usethis::use_directory('raw-data/place_details')

# restaurant_details %>%
#   mutate(score = rating*log(user_ratings_total)) %>%
#   arrange(desc(score))




# test_output %>% distinct(name,lat,lng) %>% leaflet::leaflet() %>% leaflet::addTiles() %>% leaflet::addMarkers(lng = ~lng, lat = ~lat,label = ~name,
#                                                                                                               clusterOptions = leaflet::markerClusterOptions())

# test_output


# group_by(name,address) %>% add_count(sort = TRUE) %>%
#   ungroup() %>%
#   slice(1:2) %>% lapply(unique)
#
#
# test_output %>% distinct(name,lat,lng) %>% leaflet::leaflet() %>% leaflet::addTiles() %>% leaflet::addMarkers(lng = ~lng, lat = ~lat,label = ~name)

# create_dense_grid(austin_coords[1],austin_coords[2]) %>% leaflet::leaflet() %>% leaflet::addTiles() %>% leaflet::addMarkers(lng = ~lng, lat = ~lat)

#
# {
#   test_link <- test_output %>% sample_n(1) %>% pull(next_pg)
#   get_google_res(
#     google_places(key = api_key,
#                   location = c(30.286071,-97.739352),radius = 1609*10,
#                   place_type = choose_opts[1],
#                   page_token = test_link)
#   ) %>% select(name,next_pg)
# }




# example_details <-googleway::google_place_details(place_id = "ChIJM8w7rqS1RIYRhEz2-KuoqzE",key = api_key)



# results <- google_places(location = c(30.286071,-97.739352),radius = 1609*10,place_type = choose_opts[1],
#                          key = api_key,simplify = TRUE)
#
# get_google_res(results)
# results <- google_places(search_string = "Restaurants in Austin TX", key = api_key)
#
# results$results %>% as_tibble() %>% glimpse()
#

# get_google_res(results) %>% pull(next_pg) %>% unique()
#
# google_places(key = api_key,
#               location = c(30.286071,-97.739352),radius = 1609*10,
#               page_token = "AciIO2dI4WbWqjpuDTZL12ERtxDNa-uuaQfWrfmAqqBl059PGSjStlwIzsw5Fo1hhaAQNsTzOL8ast8oylz_QjgXgZNTQwHn9JsdoSgC9q6g7YTJIyGDPqGCcpoGXtE9r92WOY9Za6Mi5GeZH8ivUqi5wsA6lb65hQQuZao7DX1LARqf3gIqKN9izCxoEiRz_Q5wHv6WrS_4U-u04TVEazNZWjoddgZKy_Jprq351zvf_OzjpCLUq8sBduoR0Vo3H1TxixoDAtUUhAkQ5Em_L7ZCRh-6a7vbYQIJmyvrydwfH8COITIphQUubFSU-Sayv5j_Q2TY3Axd01vgJCjH4xXsPdLkOvXaoRxXwhw4Ov3a5D4bAkeh5QIateqcLwCyhZoRlVrmReIBGU8CXnsM4oAj8FUn8xdTmKjDKs-VBIDg7QI1fQeDX0VgHmh1KZAG") %>%
#   get_google_res()

# location_res <- results$results %>%
#   select(geometry) %>%
#   as_tibble() %>%
#   unnest() %>%
#   unnest() %>%
#   select(lat,lng)
#
# location_res
#
# results$results$opening_hours %>% glimpse()
#
# results$results %>% View()
#
# results$results %>% as_tibble() %>%
#   select(id = reference,name,business_status,price_level,rating,user_ratings_total,address = vicinity) %>% left_join(
#     location_res
#   )
#
# place_type <- results$results$types %>% map_dfr(~{
#   tibble(place_tags = unlist(.x) %>% paste(collapse = ","))
# })
#
#
#
# results$results %>% select(where(is.list)) %>%
#   as_tibble()
#   glimpse()
#   select(photos) %>% View()
#
# slice(1) %>% pull(geometry) %>% pull(location) %>% pull(lat)
#   rowwise() %>%
#   mutate(lat = map_dbl(geometry,~.x$location$lat))

# test_output %>% distinct(next_pg)
