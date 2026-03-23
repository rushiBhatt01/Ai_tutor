# from langchain.llms import Cohere
# from langchain import PromptTemplate, LLMChain
# import json
# import random


# def create_script(topic_name, level_of_explanation, age, creativity_level, humour_level):

#     age = str(age)

#     beginner = "Explain this in a simple and easy to understand way for beginners. Help them understand the intuition, logic and importance of it."

#     intermediate = "Explain the topic with a bit more complexity and depth, assuming the reader has some prior knowledge and understanding. The script must be very long and detailed."

#     advanced = "Delve into intricate details of the topic and explain it in depth. The reader has a solid foundation and is familiar with the intermediate concepts. Include more technical language, mathematical formulas, or advanced examples to provide a comprehensive understanding of the topic. Be extremely detailed and the script must be very long."

#     level_string = beginner if level_of_explanation == 'beginner' else intermediate if creativity_level == 'intermediate' else advanced

   
#     creativity_level = int(creativity_level)
#     humour_level = int(humour_level)

# # Define creativity_string based on the creativity_level
#     creativity_string = "" if creativity_level < 4 else "Be Creative while explaining the concepts to make it easier to understand." if creativity_level < 7 else "Be creative while explaining the concepts to make it easier to understand, include creative analogies while explaining."

# # Define humour_string based on the humour_level
#     humour_string = "" if humour_level < 4 else "Be a little humorous while explaining the concepts." if humour_level < 7 else "Be funny and add jokes while explaining the concepts to make it more fun to learn."
#     # Randomly select an API key
#     selected_key = json.load(open('apikeys.json', 'r'))['api_keys'][random.randint(
#         0, len(json.load(open('apikeys.json', 'r'))['api_keys'])-1)]

#     # Initialise model
#     llm = Cohere(cohere_api_key=selected_key,
#                  model='command', temperature=0.4, max_tokens=300)#changes

#     # create the template string
#     template = """Instructions:\nCreate a script for a self contained video about {topic_name} such that {age} year old can understand. Explain the key concepts. {level_string} {creativity_string} {humour_string} It should be in first person. Be cheerful and happy while explaining also make it in 100 words."""

#     # create prompt
#     prompt = PromptTemplate(template=template, input_variables=[
#                             "topic_name", "age", "level_string", "creativity_string", "humour_string"])

   

#     # Create and run the llm chain
#     llm_chain = LLMChain(prompt=prompt, llm=llm)
#     response = llm_chain.run(topic_name=topic_name, age=age, creativity_string=creativity_string,
#                              humour_string=humour_string, level_string=level_string)

#     return response

import cohere
import json
import random

def create_script(topic_name, level_of_explanation, age, creativity_level, humour_level):
    age = str(age)

    # Define explanation strings
    beginner = "Explain this ... intuition, logic and importance."
    intermediate = "Explain ... very long and detailed."
    advanced = "Delve into ... Be extremely detailed and the script must be very long."
    if level_of_explanation == 'beginner':
        level_string = beginner
    elif level_of_explanation == 'intermediate':
        level_string = intermediate
    else:
        level_string = advanced

    creativity_level = int(creativity_level)
    humour_level = int(humour_level)

    creativity_string = (
        "" if creativity_level < 4
        else "Be Creative while explaining the concepts to make it easier to understand."
        if creativity_level < 7
        else "Be creative while explaining the concepts ... include creative analogies while explaining."
    )

    humour_string = (
        "" if humour_level < 4
        else "Be a little humorous while explaining the concepts."
        if humour_level < 7
        else "Be funny and add jokes while explaining the concepts to make it more fun to learn."
    )

    # Pick a random API key
    import os
    from dotenv import load_dotenv
    load_dotenv()
    selected_key = os.environ.get("COHERE_API_KEY")

    co = cohere.ClientV2(selected_key)  # Use ClientV2 for the new API style

    prompt_content = (
        f"Instructions:\n"
        f"elaborate about {topic_name} such that a {age}-year-old can understand. "
        f"Explain the key concepts. {level_string} {creativity_string} {humour_string} "
        f"It should be in first person. Be Creative and happy while explaining"
        f"There should be accurate information without repeating prompt or using special characters.use IEEE spectrum web for refernce"
    )

    response = co.chat(
        model="command-r-plus",  # or whichever latest model you prefer
        messages=[{"role": "user", "content": prompt_content}],
        temperature=0.4,
        max_tokens=500
    )
    print(response.message.content[0].text)

    # Extract the generated text
  


create_script("deep brain stimulation using ai", "advanced", 16, 8, 5)



