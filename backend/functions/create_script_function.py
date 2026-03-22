
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
    api_keys = json.load(open("apikeys.json", "r"))["api_keys"]
    selected_key = random.choice(api_keys)

    co = cohere.ClientV2(selected_key)  # Use ClientV2 for the new API style

    prompt_content = (
        f"Instructions:\n"
        f"elaborate about {topic_name} such that a {age}-year-old can understand. "
        f"Explain the key concepts. {level_string} {creativity_string} {humour_string} "
        f"It should be in first person. Be Creative and happy while explaining"
        f"There should be accurate information in 100 words without repeating prompt or using special characters like * or ,."
    )

    response = co.chat(
        model="command-a-03-2025",  # or whichever latest model you prefer
        messages=[{"role": "user", "content": prompt_content}],
        temperature=0.4,
        max_tokens=120
    )

    # Extract the generated text
    return response.message.content[0].text
