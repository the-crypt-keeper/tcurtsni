import streamlit as st
import requests
import json
import os
from transformers import AutoTokenizer

# Streamlit app configuration
st.set_page_config(page_title="Tcurtsni: You're the AI now", page_icon="🤖")

# Sidebar for configuration
st.sidebar.title("Configuration")
system_prompt = st.sidebar.text_area("System Prompt", value="You are a helpful personal assistant.")
server_url = st.sidebar.text_input("llama.cpp server base", value=os.getenv('LLAMA_API_URL',"http://127.0.0.1:8080"))
tokenizer_name = st.sidebar.text_input("Tokenizer", value="meta-llama/Meta-Llama-3-8B-Instruct")
supress_bos = st.sidebar.checkbox('Supress BOS', value=True)
start_button = st.sidebar.button("Start/Reset Conversation")

if "messages" not in st.session_state: st.session_state.messages = []
if "tokenizer" not in st.session_state: st.session_state.tokenizer = None
if "model_name" not in st.session_state: st.session_state.model_name = None
       
# Initialize session state
if start_button:
    try:
        model_name = requests.get(server_url+'/v1/models').json()['data'][0]['id']
    except Exception as e:
        st.sidebar.error('Failed to load model name, check server url: '+str(e))
        model_name = None

    try:
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, add_bos_token=False)
    except Exception as e:
        st.sidebar.error('Failed to load tokenizer: '+str(e))
        
    if model_name is not None and tokenizer is not None:
        st.session_state.messages = [{"role": "system", "content": system_prompt}]
        st.session_state.tokenizer = tokenizer
        st.session_state.model_name = model_name

if st.session_state.model_name is not None:
    st.sidebar.markdown(f'`{st.session_state.model_name}` loaded.')
    
# Functions
def inverse_chat_history(messages):
    bos_supress = { "bos_token": '' } if supress_bos else {}
    prompt = st.session_state.tokenizer.apply_chat_template(messages+[{"role": "user", "content": "<<CLIP>>"}], tokenize=False, add_generation_prompt=False, **bos_supress)
    clip_idx = prompt.find('<<CLIP>>')
    prompt = prompt[:clip_idx]
    print(prompt)
    return prompt

def stream_response(prompt):
    data = {
        "prompt": prompt,
        "top_p": 0.9,
        "n_predict": 1000,
        "stream": True
    }
    headers = {"Content-Type": "application/json"}
    completion = ''
    
    try:
        with requests.post(server_url+'/completion', headers=headers, json=data, stream=True) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        json_data = json.loads(decoded_line[6:])
                        if 'content' in json_data:
                            completion += json_data['content']
                            yield completion
                        if 'stop' in json_data and json_data['stop']:
                            break
    except requests.exceptions.RequestException as e:
        st.error(f"Error: {e}")

# Main app
st.title("Tcurtsni: You're the AI now")

# Display chat messages
for message in st.session_state.messages[1:]:  # Skip the system message
    with st.chat_message(message["role"]):
        st.write(message["content"])

# User input
if user_input := st.chat_input("AI response", disabled=(st.session_state.tokenizer is None)):
    st.session_state.messages.append({"role": "assistant", "content": user_input})
    with st.chat_message("assistant"):
        st.write(user_input)

if len(st.session_state.messages) > 0 and st.session_state.messages[-1]['role'] != 'user':
    # Generate LLM response (user message in this case)
    with st.chat_message("user"):
        response_placeholder = st.empty()
        full_response = ""
        for response in stream_response(inverse_chat_history(st.session_state.messages)):
            response_placeholder.markdown(response)
            full_response = response
        st.session_state.messages.append({"role": "user", "content": full_response})