import streamlit as st
import boto3
import configparser
from langchain_community.chains.graph_qa.neptune_sparql import NeptuneSparqlQAChain
from langchain_aws import ChatBedrock
from langchain_community.graphs import NeptuneRdfGraph
import os

logger = st.logger.get_logger(__name__)

# Load settings from config file
config = configparser.ConfigParser()
config_file_path = os.path.join(os.path.expanduser("~"), "streamlit", "settings.cfg")
config.read(config_file_path)

# Initialize chain with settings from config file
host = config.get("default", "host", fallback="")
port = config.getint("default", "port", fallback=8182)
region = config.get("default", "region", fallback="us-east-1")
model_id = config.get(
    "default", "model_id", fallback="anthropic.claude-3-sonnet-20240229-v1:0"
)

# Initialize chain lazily
chain = None

def initialize_chain(host, port, region, model_id):
    global chain

    bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    graph = NeptuneRdfGraph(
        host=host,
        port=port,
        use_iam_auth=True,
        region_name=region,
        use_https=True,
    )
    llm = ChatBedrock(model_id=model_id, client=bedrock_client)
    chain = NeptuneSparqlQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,
        top_K=10,
        return_intermediate_steps=True,
        return_direct=False,
    )
    logger.info("Chain initialized")

def app():
    pages = {
        "Settings": settings_page,
        "RAG": rag_page,
    }

    st.sidebar.title("Navigation")
    selection = st.sidebar.radio("Go to", list(pages.keys()))
    pages[selection]()

def settings_page():
    st.title("Settings")
    # Database information inputs
    host = st.text_input(
        "Neptune Host", value=config.get("default", "host", fallback="")
    )
    port = st.number_input(
        "Neptune Port", value=config.getint("default", "port", fallback=8182)
    )
    region = st.text_input(
        "AWS Region", value=config.get("default", "region", fallback="us-east-1")
    )
    # Model selection input
    model_id = st.text_input(
        "Model ID",
        value=config.get(
            "default", "model_id", fallback="anthropic.claude-3-sonnet-20240229-v1:0"
        ),
    )
    # Save settings button
    if st.button("Save Settings"):
        config["default"] = {
            "host": host,
            "port": str(port),
            "region": region,
            "model_id": model_id,
        }
        with open(config_file_path, "w") as configfile:
            config.write(configfile)
        st.success("Settings saved successfully!")
        initialize_chain(host, port, region, model_id)  # Initialize the chain with updated settings

def rag_page():
    st.title("Retrieval Augmented Generation")
    # User query input
    query = st.text_area("Enter your query")
    # Invoke the chain when the user clicks the button
    if st.button("Submit"):
        if chain is None:
            initialize_chain(host, port, region, model_id)  # Initialize the chain with current settings
        if chain is not None:
            result = chain.invoke(query)
            # Display the final result
            st.write("Result:")
            st.write(result["result"])
            # Display the generated SPARQL query
            st.write("Generated SPARQL:")
            st.code(result["intermediate_steps"][0]["query"])
            # Display the full context
            st.write("Full Context:")
            st.json(result["intermediate_steps"][1]["context"], expanded=False)
        else:
            st.error("Chain initialization failed. Please try again.")

if __name__ == "__main__":
    app()