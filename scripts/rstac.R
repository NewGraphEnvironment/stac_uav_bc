
# testing interating with our stac collection with rstac


library(rstac)

bucket <-  "dev-imagery-uav-bc"
path_bucket <-  paste0("s3://", bucket)
f <- s3fs::s3_dir_ls(path_bucket, recurse = TRUE, type = "file")
d <- s3fs::s3_dir_ls(path_bucket, recurse = TRUE, type = "directory")
dir_out <- "/Users/airvine/Projects/gis/uav_imagery/imagery_uav_bc"

# look for the catalog.json file with grep
f[grep("catalog.json", f)]
f[grep("imagery_uav_bc.json", f)]
f[grep("collections.json", f)]

# delete the old one
s3fs::s3_file_delete(paste0(path_bucket,"/", "catalog.json"))


# now push it up to the bucket
s3fs::s3_file_copy(
  path = paste0(dir_out,"/", "catalog.json"),
  new_path = paste0(path_bucket,"/", "catalog.json"),
  ContentType = "application/json"
)


# when we load the catalog json we need to make it the website config file
s3 <- paws::s3()
s3$put_bucket_website(
  Bucket = "dev-imagery-uav-bc",
  WebsiteConfiguration = list(
    IndexDocument = list(Suffix = "catalog.json")
  )
)

r <- s3$get_bucket_website(
  Bucket = "dev-imagery-uav-bc")

r$IndexDocument


################################################################################################################
#---------------------------------------------test with brazil cube---------------------------------------------------
################################################################################################################

s_obj <- stac("https://brazildatacube.dpi.inpe.br/stac/")
get_request(s_obj)
collections_obj <- rstac::collections(s_obj, collection_id = "CB4-16D-2") |> 
  rstac::get_request()

t_obj <- s_obj %>%
  rstac::stac_search(collections = "CB4-16D-2",
                     bbox = c(-47.02148, -17.35063, -42.53906, -12.98314),
                     limit = 100) %>% 
  rstac::get_request()



################################################################################################################
#--------------------------------------------------uav-imagery-bc---------------------------------------------------
################################################################################################################

# important to note that our id is incorrect and may be cause of issues. should be imagery-uav-bc

# now we try with our stac but we don't have an api so it doesn't happen
url <- "http://dev-imagery-uav-bc.s3-website-us-west-2.amazonaws.com"
# url <- "https://dev-imagery-uav-bc.s3.amazonaws.com/catalog.json"
s_obj <- rstac::stac(url)


# this part works
rstac::get_request(s_obj)

rstac::stac_version(s_obj)
rstac::stac_type(s_obj)

collections_obj <- rstac::collections(s_obj, collection_id = "uav-imagery-bc") |> 
  rstac::get_request()


# this of course works
collection_url <- "http://dev-imagery-uav-bc.s3-website-us-west-2.amazonaws.com/collections/imagery_uav_bc.json"
response <- httr::GET(collection_url)


# this doesn't work yet
it_obj <- s_obj %>%
  stac_search(collections = "uav-imagery-bc",  # Use your collection ID
              bbox = c(-130, 48, -114, 60),   # Adjust for BC (if needed)
              limit = 100) %>% 
  get_request()


