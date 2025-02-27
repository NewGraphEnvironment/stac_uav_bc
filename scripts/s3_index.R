# this file is not necessary.  We can serve the files in a table in this repo as gitpages and get a far superior
# product. leaving here for now in case there is something useful but doubt it

# lets make a simple index for the collection where the user can get at all the tiffs
?ngr::ngr_s3_files_to_index
bucket <-  "dev-imagery-uav-bc"
path_bucket <-  paste0("s3://", bucket)
f <- s3fs::s3_dir_ls(path_bucket, recurse = TRUE, type = "file")
dir_out <- 'data/out'


# burn to index file
# ngr::ngr_s3_files_to_index(
#   files = f,
#   dir_output = dir_out,
#   header1 = path_bucket,
#   ask = FALSE
# )



# now push it up to the bucket
s3fs::s3_file_copy(
  path = paste0(dir_out,"/", "index.html"),
  new_path = paste0(path_bucket,"/", "index.html")
)

# see if it is there
s3fs::s3_dir_ls(path_bucket)

s3$get_bucket_website(
  Bucket = "dev-imagery-uav-bc"
)

s3$copy_object(
  Bucket = "dev-imagery-uav-bc",
  Key = "index.html",
  CopySource = paste("dev-imagery-uav-bc", "index.html", sep = "/"),
  MetadataDirective = "REPLACE",
  ContentType = "text/html"
)

# think this works but need to test again
s3 <- paws::s3()
# #Set the bucket's website configuration using paws
s3$put_bucket_website(
  Bucket = "dev-imagery-uav-bc",
  WebsiteConfiguration = list(
    IndexDocument = list(Suffix = "index.html")
  )
)


# If that didn't work this im cmd should
# aws s3 website s3://dev-imagery-uav-bc/ --index-document index.html⁠
# 
# # see permissions
# aws s3api head-object --bucket dev-imagery-uav-bc --key index.html
# view it onthe wbsite
ngr::ngr_s3_path_to_https(path_bucket, website = TRUE)
