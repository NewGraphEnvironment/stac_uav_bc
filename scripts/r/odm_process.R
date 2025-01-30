################################################################################################################
#--------------------------------------------------bulkley 2024---------------------------------------------------
################################################################################################################
# do this first to get it done
# re-processs the uav imagery at 10cm resolution for serving online
path <- "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/skeena/bulkley/2024"
paths <- fs::dir_ls(path,
                    glob = "barren|richfield",
                    invert = TRUE) 


# ?ngr::ngr_spk_odm


args <- lapply(paths, ngr::ngr_spk_odm)

args |> 
  purrr::walk(
    ~ processx::run(
      command = "docker",
      args = .x,
      echo = TRUE
    )
  )

################################################################################################################
#--------------------------------------------------convert to COG---------------------------------------------------
################################################################################################################
# find all the images with fs that are named ortho.tif, dtm.tif or dem.tif
paths_in <- grep(
  
  "\\.xml$",
  
  fs::dir_ls(
    path = path,
    type = "file",
    glob = "*orthophoto.tif|ortho.tif|dtm.tif|dsm.tif",
    recurse = TRUE
  ),
  invert = TRUE, value = TRUE
)

# convert outpaths to be same dir structure after archive but in new directory called imagery_uav_bc
paths_out <- fs::path(
  "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/imagery_uav_bc",
  fs::path_rel(paths_in, start = "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery")
)
