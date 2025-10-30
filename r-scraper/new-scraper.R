



get_comments <- function(name,id,url,restaurant_name,match_score){
  b <- ChromoteSession$new()
  b$view()
  page <- as.character(glue::glue("{url}comments/"))
  print(page)
  b$go_to(page)
  for(i in 1:5){
    print("attempt",i)
    b$Runtime$evaluate("document.querySelector('a.btn.more_comments').click()")
    Sys.sleep(3)
  }


  doc <- b$DOM$getDocument()

  html_content <- b$Runtime$evaluate("document.documentElement.outerHTML")$result$value
  b$close()

  new_data <- read_html(html_content) %>%
    html_nodes(".comment-content") %>%
    map_dfr(~{
      tibble(comment_html = as.character(.x) %>% str_squish(),comment_text = html_text(.x,trim = TRUE) %>% str_squish())
    })

  new_data %>% mutate(name = name,id = id,restaurant_name = restaurant_name,match_score = match_score)

}

get_comments_safe <- safely(get_comments)


read_csv('r-scraper/new_rest_scrape.csv') %>%
  slice(1) %>%
  split(.$id) %>%
  map_dfr(~{
    get_comments_safe(.x$name,.x$id,.x$restaurant_url,.x$restaurant_name,.x$match_score)$result
  })
