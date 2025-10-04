library(googleway)
library(tidyverse)
api_key = Sys.getenv("google_places_api_key")

choose_opts <- c("restaurant","cafe","bar")

get_google_res <- function(google_res){
  location_res <- google_res$results$geometry$location

  next_pg <- google_res$next_page_token

  place_type <- google_res$results$types %>% map_dfr(~{
    tibble(place_tags = unlist(.x) %>% paste(collapse = ","))
  })

  new_res <- google_res$results %>% as_tibble() %>%
    print() %>%
    select(-where(is_list)) %>%
    select(id = reference,name,business_status,price_level,rating,user_ratings_total,address = vicinity) %>% bind_cols(
      location_res
    ) %>%
    bind_cols(place_type) %>%
    mutate(
      next_pg = next_pg
    )

  new_res
}

if(FALSE){
  walk(1:500,~{
    print(.x)
    if(.x == 1){
      res_ret <- google_places(location = c(30.286071,-97.739352),radius = 1609*10,place_type = choose_opts[1],
                               key = api_key,simplify = TRUE)
      this_pg <<- get_google_res(res_ret)
      print(unique(this_pg$next_pg))
    }else{
      this_pg <<- google_places(key = api_key,
                                location = c(30.286071,-97.739352),radius = 1609*10,
                                place_type = choose_opts[1],
                                page_token = unique(this_pg$next_pg)) %>% get_google_res()
    }

    write_csv(this_pg,glue::glue("raw-res/raw-res_{.x}.csv"))
    Sys.sleep(3)

  })

}



test_output <- list.files("raw-res",full.names = TRUE) %>% imap_dfr(~read_csv(.),.id = "id")

{
  test_link <- test_output %>% sample_n(1) %>% pull(next_pg)
  get_google_res(
    google_places(key = api_key,
                  location = c(30.286071,-97.739352),radius = 1609*10,
                  place_type = choose_opts[1],
                  page_token = test_link)
  ) %>% select(name,next_pg)
}




example_details <-googleway::google_place_details(place_id = "ChIJM8w7rqS1RIYRhEz2-KuoqzE",key = api_key)



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

test_output %>% distinct(next_pg)


