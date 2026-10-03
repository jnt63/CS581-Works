import os
import functions_framework
from google.cloud import storage

BUCKET_NAME = "jasont63-nta"
#directory within bucket that holds the data set of html files
DATA_DIR = "html-files-gcs/"
#client connection to GCS
client=storage.Client()

@functions_framework.http
def fetch_file(request):
    filename=None
    
    if request.method == "GET":
        #get filename from url path
        filename=request.path.lstrip("/")
    elif request.method =="POST":
        #simply either get file or get None rather than an interrupt
        req_json = request.get_json(silent=True)
        #check for 'filename' in json dict struct
        if req_json and "filename" in req_json:
            filename=req_json["filename"]
    else:
        return ("Method Not Implemented", 501   )
   
    #check to make sure there exists a file name, if not, not sure what error to put, default to 404 error
    if not filename:
        return ("Missing filename in path (GET) or JSON payload (POST)", 404)
        
    try:
        #connect to bucket that was deployed with, here it will be bucket from hw2
        blob = client.bucket(BUCKET_NAME).blob(DATA_DIR+filename)
        
        if not blob.exists():
            return ("file, {filename}, not found",404)
         
        content=blob.download_as_bytes()
        #content type should be text/html
        content_type=blob.content_type
        
        return (content,200,{"Content-Type":content_type})
    #for debugging for bugs
    except Exception as e:
        return (f"ERROR: {str(e)}", 500)
           
        
        