
SA_NAME="sa-db-check"
SA_EMAIL="${SA_NAME}@firstproject-508221.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
	gcloud iam service-accounts create $SA_NAME \
		--display-name="cloud SQL db check SA"
		
fi

#permissions to disable db
gcloud projects add-iam-policy-binding firstproject-508221 \
	--member="serviceAccount:${SA_EMAIL}" \
	--role="roles/cloudsql.editor"

gcloud functions deploy db-check \
    --gen2 \
    --runtime=python311 \
    --region=us-central1 \
    --source=./db_check \
    --entry-point=check_db \
    --trigger-http \
    --no-allow-unauthenticated \
    --service-account=${SA_EMAIL}
	
FUNCTION_URL=$(gcloud functions describe db-check --region=us-central1 --format="value(serviceConfig.uri)")

gcloud scheduler jobs create http hourly-db-check \
    --location=us-central1 \
    --schedule="0 * * * *" \
    --uri="$FUNCTION_URL" \
    --http-method=GET \
    --oidc-service-account-email=${SA_EMAIL}
