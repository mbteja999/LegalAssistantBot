import streamlit as st
import boto3
import json
import os

# --- AWS Configuration ---
# Access secrets from secrets.toml
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_DEFAULT_REGION"] # Or a specific region if you prefer

# Replace with your actual Bedrock Agent details
BEDROCK_AGENT_ID = "SFDUD3EGTI" # e.g., "XXXXXXXXXX"
BEDROCK_AGENT_ALIAS_ID = "OSF2IUBKUI" # e.g., "TSTALIAS"
LAMBDA_FUNCTION_NAME = "Trail2" # The name of your Lambda function

# Initialize AWS clients
# Pass credentials explicitly when using st.secrets for boto3 client
bedrock_agent_runtime = boto3.client(
    'bedrock-agent-runtime',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)
lambda_client = boto3.client(
    'lambda',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

st.set_page_config(page_title="Legal Assistant Bot", page_icon="⚖️")

st.title("⚖️ Legal Assistant Bot")
st.markdown("Ask your legal questions and get an answer, then receive an email confirmation!")

# --- User Input Form ---
with st.form("legal_inquiry_form"):
    user_name = st.text_input("Your Name", placeholder="John Doe")
    user_email = st.text_input("Your Email ID", placeholder="john.doe@example.com")
    user_question = st.text_area("Your Legal Question", placeholder="e.g., What are the legal implications of a contract breach?", height=150)

    submitted = st.form_submit_button("Get Answer & Send Email")

    if submitted:
        if not user_name or not user_email or not user_question:
            st.error("Please fill in all the required fields (Name, Email, and Question).")
        else:
            st.info("Processing your request... Please wait.")
            try:
                # 1. Interact with Bedrock Agent
                st.write("Asking Bedrock Agent for an answer...")
                response_from_bedrock = bedrock_agent_runtime.invoke_agent(
                    agentId=BEDROCK_AGENT_ID,
                    agentAliasId=BEDROCK_AGENT_ALIAS_ID,
                    sessionId=str(os.urandom(16).hex()), # Generate a unique session ID
                    inputText=user_question,
                    enableTrace=True
                )

                # Parse the response from Bedrock
                event_stream = response_from_bedrock['completion']
                bedrock_answer = ""
                for event in event_stream:
                    if 'chunk' in event:
                        bedrock_answer += event['chunk']['bytes'].decode('utf-8')

                if bedrock_answer:
                    st.success("✅ Bedrock Agent's Answer:")
                    st.write(bedrock_answer)

                    # 2. Invoke Lambda Function
                    st.write("Sending data to Lambda function for saving and email...")
                    lambda_payload = {
                        "name": user_name,
                        "email": user_email,
                        "question": user_question,
                        "answer": bedrock_answer
                    }

                    response_from_lambda = lambda_client.invoke(
                        FunctionName=LAMBDA_FUNCTION_NAME,
                        InvocationType='RequestResponse', # Synchronous invocation
                        Payload=json.dumps(lambda_payload)
                    )

                    lambda_response_payload = json.loads(response_from_lambda['Payload'].read().decode("utf-8"))

                    if response_from_lambda['StatusCode'] == 200:
                        if 'error' in lambda_response_payload:
                            st.error(f"❌ Error from Lambda: {lambda_response_payload['error']}")
                        else:
                            st.success(f"🎉 Success! Request processed and email sent to {user_email}.")
                            st.write(f"Reference ID: **{lambda_response_payload.get('booking_id', 'N/A')}**")
                            st.write(f"Email Status Code: **{lambda_response_payload.get('email_status', 'N/A')}**")
                            if lambda_response_payload.get('email_error'):
                                st.warning(f"Email Sending Warning: {lambda_response_payload['email_error']}")
                    else:
                        st.error(f"❌ Failed to invoke Lambda function. Status Code: {response_from_lambda['StatusCode']}")
                        st.json(lambda_response_payload)
                else:
                    st.warning("⚠️ Bedrock Agent did not return an answer. Please try rephrasing your question.")

            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.exception(e) # Display full traceback for debugging

st.markdown("---")
st.markdown("Developed with Streamlit, AWS Bedrock, Lambda, DynamoDB, and SendGrid.")