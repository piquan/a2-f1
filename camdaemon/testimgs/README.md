These test images are taken from the USC-SIPI image database's "motion"
sequence.  See http://sipi.usc.edu/database/database.php?volume=sequences

They were postprocessed with ImageMagick using:

    for f in motion*.tiff ; do
        convert $f -resize "640x640^" -gravity center -crop 640x480+0+80 +repage -normalize $f.jpg
    done
    
and then renamed accordingly.