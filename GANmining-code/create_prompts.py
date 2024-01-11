from __future__ import annotations
import itertools
import logging
from typing import List, Optional
from pydantic import BaseModel
import random
import pandas as pd
import numpy as np
import openai
import os
import json
from rich.progress import track
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)

class Topic(BaseModel):
    topic: str
    mixing: int
    parent: Optional[Topic] = None


class Exercise(BaseModel):
    exercise: str
    topic: Topic


class Query(BaseModel):
    query: str
    topic_1: Topic
    topic_2: Topic


def create_subtopic_query(topic: str, n: int) -> str:
    logging.info(f"Creating subtopic query for {topic} with {n} subtopics")
    return f"""For a textbook on generative AI, Autonomous assistants, and efficient data processing: give me {n} subtopics of {topic}, formatted as a Python list. 
    Just provide the titles and give no explanation.
    Format the result as Python list.
    INCLUDE NOTHING OTHER THAN THE PYTHON LIST.
    """


def create_prompt_query(topic_1: Topic, topic_2: Topic, profession: str) -> str:
    logging.info(f"Creating prompt query for {topic_1.topic} and {topic_2.topic} for a {profession}")
    query = f'''
            Create a code completion exercise on the intersection of “{topic_1.topic}” and “{topic_2.topic}”.  
            Write it for a {profession}. 

            The exercise must be of the style: 

            ```
            def name(args):

            """Docstring explaining the exercise"""

            python code to solve the exercise
            ```

            NO CLASSES

            MAKE IT VERY DIFFICULT
            '''
    query = "\n".join([m.lstrip() for m in query.strip().split("\n")])
    return query


def create_subtopics(topic: Topic, n: int, retries: int = 1000000) -> List[Topic]:
    success = False
    query = create_subtopic_query(topic.topic, n)
    logging.info(f"Query: {query}")
    for i in range(retries):
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert programmer and logician."},
                    {"role": "user", "content": query},
                ],
                temperature=1.5,
            )

            result = [
                Topic(topic=i, mixing=topic.mixing, parent=topic)
                for i in eval(completion.choices[0].message["content"])
            ]
            success = True
        except Exception:
            logging.error(f"Generation failed for prompt, retrying {i + 1}/{retries}")
        else:
            break

    if success:
        logging.info("Generation successful")
        return result
    else:
        logging.error("Generation failed after all retries")
        return []


def create_prompts(
    topic: Topic,
    combination_options: List[Topic],
    professions: List[str],
    n: int,
) -> List[Query]:
    logging.info(f"Creating prompts for {topic.topic}")
    random.shuffle(combination_options)
    prompts: List[Query] = []

    for loc_topic in combination_options:
        if len(prompts) == n:
            break

        if loc_topic.mixing and loc_topic.parent != topic.parent:
            profession = professions[np.random.randint(0, len(professions))]
            query = create_prompt_query(topic, loc_topic, profession)
            prompts.append(Query(query=query, topic_1=topic, topic_2=loc_topic))

    return prompts


if __name__ == "__main__":
    logging.info("Starting main execution")
    # Load list of topics
    API_KEY = os.environ["API_PASSWORD"]
    TOPICS_PATH = "tree/topics.csv"
    openai.api_key = API_KEY

    topics = pd.read_csv(TOPICS_PATH)
    topics = topics.fillna(0)
    topics = topics.iloc[:, :3]
    topics.Topic = topics.Topic.str.split(".").str[1]
    topics.Use = topics.Use.astype(int)
    topics.Mixing = topics.Mixing.astype(int)
    topics_df = topics[topics.Use == 1].reset_index(drop=True)
    topics_df = topics_df.drop("Use", axis=1)
    topics_list = list(zip(topics_df.Topic, topics_df.Mixing))

    # Debug mode to create few prompts
    DEBUG = False
    if DEBUG:
        n_base_topics = 5
        n_combinations = 2
    else:
        n_base_topics = len(topics_df)
        n_combinations = 200

    root = Topic(topic="Python", mixing=1)
    base_topics = [
        Topic(topic=top, mixing=mix, parent=root)
        for (top, mix) in zip(topics_df.Topic, topics_df.Mixing)
    ]
    MAX_THREADS = os.getenv('MAX_THREADS', default=12)
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        subtopics = list(executor.map(create_subtopics, base_topics[:n_base_topics], [10]*len(base_topics[:n_base_topics])))
    subtopics_list = list(itertools.chain(*subtopics))
    subtopics_json = json.dumps([x.dict() for x in subtopics_list])

    with open("tree/subtopics.json", "w") as outfile:
        outfile.write(subtopics_json)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        subsubtopics = list(executor.map(create_subtopics, itertools.chain(*subtopics), [5]*len(list(itertools.chain(*subtopics)))))
    subsubtopics_list = list(itertools.chain(*subsubtopics))
    subsubtopics_json: str = json.dumps([x.dict() for x in subsubtopics_list])

    with open("tree/subsubtopics.json", "w") as outfile:
        outfile.write(subsubtopics_json)

    with open("tree/professions.json", "r") as openfile:
        # Reading from json file
        professions = list(json.load(openfile))

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        prompts = list(executor.map(create_prompts, itertools.chain(*subsubtopics), [subsubtopics_list]*len(list(itertools.chain(*subsubtopics))), [professions]*len(list(itertools.chain(*subsubtopics))), [n_combinations]*len(list(itertools.chain(*subsubtopics)))))

    prompts_list = list(itertools.chain(*prompts))
    prompts_json = json.dumps([p.dict() for p in prompts_list])
    with open("tree/prompts.json", "w") as outfile:
        outfile.write(prompts_json)
