# this converts to cogs directly in the imagery_uav_bc directories (makes them first) so all we need to do is run the
# stac build and sync to aws

# It is not that efficient but it takes a ton of fussing to figure out which cogs are already generated so at this
# point - rather than do that we just rebuild the entire directory every time.  

# first we define where we are putting the latest run
dir_out <- "/Users/airvine/Projects/gis/uav_imagery/imagery_uav_bc"


################################################################################################################
#--------------------------------------------------convert to COG---------------------------------------------------
################################################################################################################
# find all the images with fs that are named ortho.tif, dtm.tif or dem.tif
# path <- "/Users/airvine/Projects/gis/uav_imagery/skeena/bulkley"
path <- "/Users/airvine/Projects/gis/uav_imagery/skeena"
## for this we added 
grep_this <- "bulkley/2025"
invert_this <- FALSE


# here is a subset of Fraser 
path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/fraser/nechacko"
# this regex pattern ($^) matches the end of a string immediately after the start, which is impossible, ensuring that nothing is filtered out
grep_this <- "$^"
invert_this <- TRUE

# here is kyspiox, zymoetz and babine
path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/skeena"
# this regex pattern ($^) matches the end of a string immediately after the start, which is impossible, ensuring that nothing is filtered out
grep_this <- "/babine/|/kispiox/|/zymoetz/"
invert_this <- FALSE




# here is mackenzie
path <- "/Users/airvine/Projects/gis/uav_imagery/mackenzie"
# this regex pattern ($^) matches the end of a string immediately after the start, which is impossible, ensuring that nothing is filtered out
grep_this <- ""
invert_this <- FALSE

paths_in_raw <- grep(
  
  "\\.xml$",
  
  fs::dir_ls(
    path = path,
    type = "file",
    glob = "*orthophoto.tif|ortho.tif|dtm.tif|dsm.tif",
    recurse = TRUE
  ),
  invert = TRUE, 
  value = TRUE
)


# now - we have already processes the imagery for some so we will not repeat.  we will filter out those that contain our grep_this
paths_in <- grep(grep_this, paths_in_raw, invert = invert_this, value = TRUE)


# convert outpaths to be same dir structure after archive but in new directory called imagery_uav_bc
paths_out <- fs::path(
  dir_out,
  fs::path_rel(
    paths_in, 
    start = "/Users/airvine/Projects/gis/uav_imagery"
  )
)

# we don't need to subset for Mckenzieso we just transfer object name
paths_in <- paths_in_raw


args_stub <- c('run', '-n', 'dff', 'rio', 'cogeo', 'create')

# for each file add the a pth_in and a path_out to the args_stub (ex. c('run', '-n', 'dff', 'rio', 'cogeo', 'create', 'path_in', 'path_out')
args <- purrr::map2(paths_in, paths_out, ~ c(args_stub, .x, .y))

# create the directories we are burning to

fs::dir_create(
  fs::path_dir(
    paths_out
  )
)


# Define the command and working directory
command <- "conda"

system_run <- function(args){
  result <- tryCatch({
    processx::run(
      command,
      args = args,
      echo = TRUE,            # Print the command output live
      # wd = working_directory, # Set the working directory
      spinner = TRUE        # Show a spinner
      # timeout = 60            # Timeout after 60 seconds
    )
  }, error = function(e) {
    # Handle errors: e.g., print a custom error message
    cat("An error occurred: ", e$message, "\n")
    NULL  # Return NULL or another appropriate value
  })
  
  # Check if the command was successful
  if (!is.null(result)) {
    cat("Exit status:", result$status, "\n")
    cat("Output:\n", result$stdout)
  } else {
    cat("Failed to execute the command properly.\n")
  }
}

purrr::walk(args, system_run)

# We are just manually copying over the files into the /Users/airvine/Projects/gis/uav_imagery/stac location
# note that we put overwrite as FALSE so that we don't update the time stamps so don't sync new data to s3.  if 
# we thought therre were actual changes we would changes that

dir_in <- "/Users/airvine/Projects/gis/uav_imagery/imagery_uav_bc"
dir_out <- "/Users/airvine/Projects/gis/uav_imagery/stac/dev/imagery_uav_bc"
ngr::ngr_fs_copy_if_missing(dir_in, dir_out)

dir_in <- "/Users/airvine/Projects/gis/uav_imagery/imagery_uav_bc"
dir_out <- "/Users/airvine/Projects/gis/uav_imagery/stac/prod/imagery_uav_bc"

ngr::ngr_fs_copy_if_missing(dir_in, dir_out)

