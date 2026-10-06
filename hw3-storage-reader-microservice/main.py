import os
import functions_framework
import json
from google.cloud import storage, pubsub_v1


BUCKET_NAME = "jasont63-nta"
#directory within bucket that holds the data set of html files
DATA_DIR = "html-files-gcs/"

TOPIC_ID= "GET_POST_SA"
PROJECT_ID="firstproject-508221"
FORBIDDEN_CTRY=["north korea", "iran", "cuba", "myanmar", "iraq", "libya", "sudan", "zimbabwe", "syria"]
#client connection to GCS
client=storage.Client()

publisher = pubsub_v1.PublisherClient()
topic_path=publisher.topic_path(PROJECT_ID,TOPIC_ID)

def log_struct_msg(severity, msg, payload):
    struct_entry= {
        "severity":severity,
        "message":msg,
        "event_details":payload,
        }
    print(json.dumps(struct_entry))

@functions_framework.http
def fetch_file(request):
    
    country=request.headers.get("X-country","").strip().lower()
    
    if country in FORBIDDEN_CTRY:
        error_msg = f"permission denied for country: {country}"
        
        payload={
            "event": "Permission Denied",
            "method": request.method,
            "country": country,
            "status_code":400,          
        }
        log_struct_msg("ERROR",error_msg,payload)
        data_bytes = json.dumps(payload).encode("utf-8")
        publisher.publish(topic_path ,data_bytes)
        print(f"[PRINT LOG] 400 FORBIDDEN: {error_msg}")
        return ("PERMISSION DENIED",400)
    
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
        payload={
            "event":"Method Not Implemented",
            "method": request.method,
            "status_code":501
        }
        error_msg=f"Method Not Implemented: {request.method}"
        log_struct_msg("ERROR", f"Not Implemented: {request.method}",payload)
        print(f"[PRINT LOG] 501 ERROR: {error_msg}")
        return("Method not Implemented", 501)   
   
    #check to make sure there exists a file name, if not, not sure what error to put, default to 404 error
    #if not filename:
       # return ("Missing filename in path (GET) or JSON payload (POST)", 404)
        
    try:
        #connect to bucket that was deployed with, here it will be bucket from hw2
        blob = client.bucket(BUCKET_NAME).blob(DATA_DIR+filename)
        
        if not blob.exists():
            error_msg=f"File {filename} not found in {BUCKET_NAME}"
            print(f"[PRINT LOG] 404 ERROR: {error_msg}")
            payload={
                "event":"File Not Found",
                "file":filename,
                "status_code": 404,
            }
            log_struct_msg("ERROR",error_msg,payload)
            return (error_msg,404)
         
        content=blob.download_as_bytes()
        #content type should be text/html
        content_type=blob.content_type
       
        payload= {
            "event":"Success",
            "file":filename,
            "status_code":200,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        publisher.publish(topic_path,data_bytes)
        print(f"[PRINT LOG] 200 OK: Successfully served file '{filename}'.")
        
        return (content,200,{"Content-Type":content_type})
    #for debugging
    except Exception as e:
        return (f"ERROR: {str(e)}", 500)
           
        
        