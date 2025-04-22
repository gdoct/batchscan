this app should be changed to become a web application. 
this web app should have two functions: 
 * display photos in the database
    a simple photo viewer that allows the user to select a folder, and then displays the photos in that folder along with the stored metadata and tags
 * start/stop scan
    there can be a background batch_scanner running.
    the user can start or stop the background scanner. 
    there is only one background scanner on the server, not one per user. 
    the user can set the path and start the background scanner. 
    the scanner will keep running until finished or the use stops it
    the site will display scanner activity in an activity panel
    if running, it will display the current image being processed and a percentage

