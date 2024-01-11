import json
import os
import sys
import asyncio
import openai

async def process_script(script_path):
    with open(script_path, 'r') as file:
        lines = file.readlines()

    # Get the user instruction for the entire script
    user_instruction = await get_user_instruction(''.join(lines))
    modified_scripts = []

    for i, line in enumerate(lines):
        # Current snapshot of the script up to the current line
        current_script = ''.join(lines[:i+1])
        api_response = await call_openai_api(current_script)

        # Add the comment to the correct line in the entire script
        chosen_script = ''.join(lines[:i]) + lines[i].rstrip() + " # " + api_response["correct_comment"] + '\n' + ''.join(lines[i+1:])
        # For the rejected field, replace the current line with the incorrect version and add the comment
        rejected_line = ''.join(lines[:i]) + api_response["incorrect_line"] + " # " + api_response["incorrect_comment"]

        modified_scripts.append({
            "prompt": [user_instruction],
            "chosen": [chosen_script],
            "rejected": [rejected_line]
        })

    return modified_scripts

async def get_user_instruction(script):
    prompt = "Reply ONLY with an instruction that a user might give that would require you to write the following script. Ensure the instruction you generate is accurately satisfied by the script.\n\n" + script

    response = await openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    )

    return response["choices"][0]["message"]["content"].strip()

async def call_openai_api(script):
    prompt = "Please rewrite ONLY the final typed line of this code:\n" + script + "\n\n" + \
             "Then, on a newline directly below it, write an alternate version of the line..."

    response = await openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    )

    response_text = response["choices"][0]["message"]["content"]
    lines = response_text.strip().split('\n')
    if len(lines) < 2 or '#' not in lines[0] or '#' not in lines[1]:
        return await call_openai_api(script)

    correct_comment = lines[0].split('#')[1].strip()
    incorrect_comment = lines[1].split('#')[1].strip()
    incorrect_line = lines[1].split('#')[0].strip()

    return {
        "correct_comment": correct_comment,
        "incorrect_line": incorrect_line,
        "incorrect_comment": incorrect_comment
    }

async def process_folder(folder_path):
    script_paths = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith('.py')]
    tasks = [process_script(script_path) for script_path in script_paths]

    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        output_path = os.path.join(folder_path, f'output_{i}.jsonl')
        with open(output_path, 'w') as file:
            for script in result:
                file.write(json.dumps(script) + '\n')

if __name__ == "__main__":
    folder_path = sys.argv[1]
    asyncio.run(process_folder(folder_path))
