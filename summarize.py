import os
import openai
from dotenv import load_dotenv
from fc import *
import pandas as pd

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def get_replies_from_post_id_sql_query(hash):
    sql_query = """
        WITH UserData AS (
            SELECT
                u.fid,
                MAX(CASE WHEN u.type = 2 THEN u.value END) AS display_name,
                MAX(CASE WHEN u.type = 1 THEN u.value END) AS avatar_url,
                MAX(CASE WHEN u.type = 6 THEN u.value END) AS handle
            FROM user_data u
            WHERE u.deleted_at IS NULL
            GROUP BY u.fid
        ),

        CastReactions AS (
            SELECT 
                target_hash,
                SUM(CASE WHEN reaction_type = 1 THEN 1 ELSE 0 END) AS likes,
                SUM(CASE WHEN reaction_type = 2 THEN 1 ELSE 0 END) AS shares
            FROM 
                reactions
            WHERE 
                target_hash IS NOT NULL
            GROUP BY 
                target_hash
        ),

        CastReplies AS (
            SELECT 
                parent_hash,
                COUNT(*) AS replies
            FROM 
                casts
            WHERE 
                parent_hash IS NOT NULL
            GROUP BY 
                parent_hash
        )

        SELECT
            cast(encode(c.hash, 'hex') as text) as hash,
            c.fid,
            ud.display_name,
            ud.handle,
            ud.avatar_url,
            c.text,
            CASE WHEN c.parent_hash IS NULL THEN 'post' ELSE 'comment' END AS post_type,
            c.timestamp,
            COALESCE(cr.likes, 0) AS likes,
            COALESCE(cr.shares, 0) AS shares,
            COALESCE(crp.replies, 0) AS replies
        FROM
            casts c
        JOIN   
            UserData ud ON c.fid = ud.fid
        LEFT JOIN
            CastReactions cr ON c.hash = cr.target_hash
        LEFT JOIN
            CastReplies crp ON c.hash = crp.parent_hash
        WHERE
            CONCAT('0x', cast(encode(c.parent_hash, 'hex') as text)) = '"""+hash+"""' AND c.parent_hash IS NOT NULL
        AND c.deleted_at IS NULL
        """
    return sql_query

def get_replies_from_post_id(hash):

    sql_query = get_replies_from_post_id_sql_query(hash)
    
    # run query
    df = run_query(sql_query)
    return df

def summarize_conversation(hash):

    df = get_replies_from_post_id('0x'+hash)
    df['score'] = df['likes'] + df['shares'] + df['replies']
    df.sort_values(by=['score'], inplace=True, ascending=False)
    
    messages =[]
    prompt = f"Summarize the comment section below into approximatly 250 characters. Start with a very quick assesment of the mood and sentiment of the users. Distill top 3 topics or ideas. Summary should be self-contained and ready to be published online as a reflection. \n"
    for i, row in df.head(50).iterrows():
        prompt += f"User {row.handle} said: {row.text} \n"
    
    messages.append({"role": "user", "content": prompt})

    full_response = ""
    openai.api_key = OPENAI_API_KEY
    for response in openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in messages
            ],
            stream=True,
        ):
            full_response += response.choices[0].delta.get("content", "")
            
    return full_response