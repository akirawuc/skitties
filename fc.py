import os
from dotenv import load_dotenv
import psycopg2
import pandas as pd
import requests
import json
from datetime import datetime, timedelta, date, timezone

load_dotenv()

MBD_API_API = os.getenv("MBD_API_API")

# QUERY EXECUTION
# get PGHOST, PGDATABASE, PGUSER, PGPASSWORD
PGHOST = os.getenv("PGHOST")
PGDATABASE = os.getenv("PGDATABASE")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")

FARCASTER_CLIENT_URL_REDIRECT = "https://warpcast.com/"

def run_query(sql_query, item_list=None):
    try:
        #connect to postgres
        conn = psycopg2.connect(
            host=PGHOST,
            database=PGDATABASE,
            user=PGUSER,
            password=PGPASSWORD)

        # Create a cursor
        cursor = conn.cursor()
        
        # Execute the SQL query
        if item_list is not None and len(item_list) != 0:
            cursor.execute(sql_query, (tuple(item_list),))
        else:
            cursor.execute(sql_query)
            
        # Fetch all results
        results = cursor.fetchall()

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]

        # Convert results to DataFrame
        df = pd.DataFrame(results, columns=column_names)

        # Close the cursor and the connection
        cursor.close()

        # df = pd.read_sql(sql_query, conn)
        # st.write(df)
        
        #close connection
        conn.close()

        return df
    except Exception as e:
        print(f"Personalize Error: {e}")
    
def get_latest_posts_sql_query(sql_condition, items_per_page, offset):
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
            c.parent_fid, 
            c.parent_url,
            COALESCE(cr.likes, 0) AS likes,
            COALESCE(cr.shares, 0) AS shares,
            COALESCE(crp.replies, 0) AS replies,
            CASE 
                WHEN c.parent_hash IS NULL THEN 'post'
                ELSE 'reply'
            END AS post_type
        FROM 
            casts c
        JOIN 
            UserData ud ON c.fid = ud.fid
        LEFT JOIN 
            CastReactions cr ON c.hash = cr.target_hash
        LEFT JOIN 
            CastReplies crp ON c.hash = crp.parent_hash
        WHERE
            """+ sql_condition +""" 
            AND c.deleted_at IS NULL
        ORDER BY 
            c.timestamp DESC
        LIMIT """+ str(items_per_page) + """ OFFSET """ + str(offset) 
    return sql_query

def get_latest_posts(sql_condition, items_per_page, offset):

    sql_query = get_latest_posts_sql_query(sql_condition, items_per_page, offset)

    # run query
    df = run_query(sql_query)
    return df

def get_posts_from_item_ids_sql_query(items_ids_list):
        
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
        WHERE cast(encode(c.hash, 'hex') as text) IN %s
        AND c.deleted_at IS NULL
        """
    return sql_query

def get_posts_from_item_ids(items_ids_list):

    sql_query = get_posts_from_item_ids_sql_query(items_ids_list)

    # run query
    df = run_query(sql_query, item_list=items_ids_list)
    return df

def parse_query(query):
    """Parse user input into structured tokens."""
    tokens = []
    i = 0
    while i < len(query):
        # st.write(i, query[i])
        if query[i] == '(':
            j = i + 1
            depth = 1
            while j < len(query) and depth > 0:
                if query[j] == '(':
                    depth += 1
                elif query[j] == ')':
                    depth -= 1
                j += 1
            tokens.append(parse_query(query[i + 1:j - 1]))
            i = j
        elif query[i] == ' ':
            i += 1
        elif query[i] == '"':
            start = i
            if start > 0 and query[start-1] == '-':  # Handle negation with exact match
                start -= 1
            j = i + 1
            while j < len(query) and query[j] != '"':
                j += 1
            tokens.append(query[start:j+1])
            i = j + 1
        else:
            start = i
            j = i
            
            # Check for operator tokens
            
            j += len('-fid:')
            if query.startswith('-fid:', j):
                while j < len(query) and query[j] not in [' ', '(', ')', '"']:
                    j += 1
            j += len('-from:')
            if query.startswith('-from:', j):
                while j < len(query) and query[j] not in [' ', '(', ')', '"']:
                    j += 1
            j += len('-parent_fid:')
            if query.startswith('-fid:', j):
                while j < len(query) and query[j] not in [' ', '(', ')', '"']:
                    j += 1
            j += len('-parent_url:')
            if query.startswith('-parent_url:', j):
                while j < len(query) and query[j] not in [' ', '(', ')', '"']:
                    j += 1
            
            # If it's not an operator, it's a regular term
            else:
                j = i
                if start < len(query) and query[start] == '-' and (start+1 < len(query) and query[start+1] not in [' ', '(', ')', '"']):
                    # If a hyphen is followed by another token, it's a negation.
                    j += 1
                while j < len(query) and query[j] not in [' ', '(', ')', '"']:
                    # st.write('=>',j, query[j])
                    j += 1
            # st.write(query[start:j])
            tokens.extend(query[start:j].split())
            i = j
    return tokens

def token_to_sql(token):
    """Translate a token into its SQL equivalent."""
    
    if isinstance(token, list):  # Nested condition
        sub_conditions = [token_to_sql(t) for t in token]
        return "(" + " ".join(sub_conditions) + ")"
    elif token == 'OR':
        return 'OR'
    elif token == 'AND':
        return 'AND'
    
    elif token.startswith('-type:post'):
        return f"c.parent_hash IS NOT NULL"
    elif token.startswith('-type:reply'):
        return f"c.parent_hash IS NULL"
    elif token.startswith('type:post'):
        return f"c.parent_hash IS NULL"
    elif token.startswith('type:reply'):
        return f"c.parent_hash IS NOT NULL"

    elif token.startswith('fid:'):
        return f"c.fid = '{token.split(':')[1]}'"
    elif token.startswith('-fid:'):  
        fid = token.split(':', 1)[1]
        return f"c.fid != '{fid}'"   
    
    elif token.startswith('from:'):
        return f"ud.handle = '{token.split(':')[1]}'"
    elif token.startswith('-from:'):  
        from_user = token.split(':', 1)[1]
        return f"ud.handle != '{from_user}'"

    elif token.startswith('parent_fid:'):
        return f"c.parent_fid = '{token.split(':')[1]}'"
    elif token.startswith('-parent_fid:'):  
        parent_fid = token.split(':', 1)[1]
        return f"c.parent_fid != '{parent_fid}'"   

    elif token.startswith('parent_url:'):
        return f"c.parent_url = '{token.split(':', 1)[1]}'"
    elif token.startswith('-parent_url:'):  
        parent_url = token.split(':', 1)[1]
        return f"c.parent_url != '{parent_url}'"   

    
    # Negate minimum likes
    elif token.startswith('-min_likes:'):
        count = token.split(':', 1)[1]
        return f"likes < {count}"
    elif token.startswith('-min_shares:'):
        count = token.split(':', 1)[1]
        return f"shares < {count}"
    elif token.startswith('-min_replies:'):
        count = token.split(':', 1)[1]
        return f"replies < {count}"

    elif token.startswith('-'):
        if len(token) != 1:
            if token[1:].startswith('"') and token[-1] == '"':  # Negation of exact match
                return "c.text NOT LIKE '%"+token[1:].replace('"',"")+"%'"
            else:
                return f"c.text NOT LIKE '%{token[1:]}%'"
        else:
            return ''
    elif token.startswith('"') and token[-1] == '"':  # Exact match
        return "c.text LIKE '%" + token.replace('"',"")+"%'"

    
    elif token.startswith('within_time:'):
        # minutes = int(token.split(':')[1].replace('min', ''))
        # time_limit = datetime.now() - timedelta(minutes=minutes)
        time_limit = token.split(':')[1]
        return f"c.created_at >= (CURRENT_TIMESTAMP - INTERVAL '{time_limit}')"
    elif token.startswith('since_time:'):
        timestamp = datetime.utcfromtimestamp(int(token.split(':')[1]))
        return f"c.created_at >= '{timestamp}'"
    elif token.startswith('until_time:'):
        timestamp = datetime.utcfromtimestamp(int(token.split(':')[1]))
        return f"c.created_at <= '{timestamp}'"
    elif token.startswith('min_likes:'):
        return f"likes >= {token.split(':')[1]}"
    elif token.startswith('min_shares:'):
        return f"shares >= {token.split(':')[1]}"
    elif token.startswith('min_replies:'):
        return f"replies >= {token.split(':')[1]}"
    else:
        return f"text LIKE '%{token}%'"

def translate_query_to_sql(query):
    """Translate user input to SQL WHERE condition."""
    
    # query = "(" + query + ")"
    # st.write(query)
    tokens = parse_query(query)
    # st.write(tokens)
    return " ".join([token_to_sql(token) for token in tokens])

def get_trending_posts(model_id, filter_values, items_per_page):
    try:

        mbd_trending_url = "https://api.mbd.xyz/v1/farcaster/trending-now"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": MBD_API_API
        }
        
        payload = {
            "user_id": '3',
            "model_id": model_id, # "farcaster-v2-trending-now-items-1day"
            "top_k": str(items_per_page)
        }

        if "item_type" in filter_values.keys():
            payload = payload | filter_values
    
        response = requests.post(mbd_trending_url, json=payload, headers=headers)

        items_list = json.loads(response.text)['body']
        item_ids_list = [item["itemId"] for item in items_list]
        return item_ids_list

    except Exception as e:
        print(f"mbd Error: {e}")

def get_popular_posts(model_id, filter_values, items_per_page):
    try:

        mbd_trending_url = "https://api.mbd.xyz/v1/farcaster/popular"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": MBD_API_API
        }
        
        payload = {
            "user_id": '3',
            "model_id": model_id, # "farcaster-v2-trending-now-items-1day"
            "top_k": str(items_per_page)
        }

        if "item_type" in filter_values.keys():
            payload = payload | filter_values
    
        response = requests.post(mbd_trending_url, json=payload, headers=headers)

        items_list = json.loads(response.text)['body']
        item_ids_list = [item["itemId"] for item in items_list]
        return item_ids_list

    except Exception as e:
        print(f"mbd Error: {e}")

def get_for_you_posts(user_id, model_id, filter_values, items_per_page):
    try:

        mbd_for_you_url = "https://api.mbd.xyz/v1/farcaster/for-you"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": MBD_API_API
        }
        
        payload = {
            "user_id": str(user_id),
            "model_id": model_id, 
            "top_k": str(items_per_page)
        }

        if "item_type" in filter_values.keys():
            payload = payload | filter_values
        
        response = requests.post(mbd_for_you_url, json=payload, headers=headers)
        
        items_list = json.loads(response.text)['body']
        item_ids_list = [item["itemId"] for item in items_list]
        
        return item_ids_list   

    except Exception as e:
        print(f"mbd Error: {e}")

def get_item_id_from_post_id_sql_query(post_id):
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
            CONCAT('0x', LEFT(cast(encode(c.hash, 'hex') as text), 9)) IN %s
        AND c.deleted_at IS NULL
        """
    return sql_query

def get_item_id_from_post_id(post_id):

    sql_query = get_item_id_from_post_id_sql_query(post_id)
  
    # run query
    df = run_query(sql_query, item_list=[post_id])
    return df

def get_similar_posts(item_id, model_id, filter_values, items_per_page):
    try:

        mbd_similar_url = "https://api.mbd.xyz/v1/farcaster/similar"
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": MBD_API_API
        }
        
        payload = {
            "item_id": str(item_id),
            "user_id": '3',
            "model_id": model_id, 
            "top_k": str(items_per_page)
        }

        if "item_type" in filter_values.keys():
            payload = payload | filter_values
        
        response = requests.post(mbd_similar_url, json=payload, headers=headers)
        
        items_list = json.loads(response.text)['body']
        item_ids_list = [item["itemId"] for item in items_list]
        
        return item_ids_list   

    except Exception as e:
        print(f"mbd Error: {e}")

def get_user_id_from_handle(handle):
    # run SQL query against 

    sql_query = """
    SELECT
        u.fid as user_id
    FROM user_data u
    WHERE u.type = 6 AND u.value = '"""+ handle + """'
    """

    # run query
    df = run_query(sql_query)
    if df.empty:
        return None
    else:
        return df.user_id[0]

def time_passed(date_str, timezone_aware=False):
    if timezone_aware:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.now()
    # st.write(date_str)
    if isinstance(date_str, str):
        
        if 'GMT' in date_str:
            date_str = date_str[:date_str.index("GMT")]
        date_str = parser.parse(date_str)
    
    delta = now - date_str
    # st.write(delta)
    if delta < timedelta(minutes=1):
        seconds = int(delta.total_seconds())
        return f"{seconds} seconds ago"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minutes ago"
    if delta < timedelta(hours=24):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hours ago"
    elif delta < timedelta(days=7):
        days = int(delta.total_seconds() / 86400)
        return f"{days} days ago"
    elif delta < timedelta(days=30):
        weeks = int(delta.total_seconds() / 604800)
        return f"{weeks} weeks ago"
    else:
        months = int(delta.total_seconds() / 2600640)
        return f"{months} months ago"

# GET FOR YOU POSTS
# get_for_you_posts(user_id = 9082, 
#                     model_id = "farcaster-v2-user-perosnalization-3exp-30days", 
#                     filter_values = {},
#                     # filter_values = {
#                     #     "item_type": ["post"],
#                     #     "start_date": "1598919338",
#                     #     "end_date": "1699524138"
#                     # }, 
#                     items_per_page = 5)

# GET TRENDING POSTS
# get_trending_posts(
#                     user_id = 2, 
#                     model_id = "farcaster-v2-trending-now-items-1day", 
#                     filter_values = {
#                         "item_type": ["post"],
#                         "start_date": "1598919338",
#                         "end_date": "1699524138"
#                     }, 
#                     items_per_page = 25
#                 )

# GET SEARCH RESULTS
# sql_condition = translate_query_to_sql("(eth AND btc)")
# df = get_latest_posts(sql_condition, 5, 1)

# GET SIMILAR POSTS
# post_link = "https://warpcast.com/dwr.eth/0x7735946a4"
# post_id = post_link.split("/")[-1]
# if len(post_id) == 11:
#     item_df = get_item_id_from_post_id(post_id)  
# print(get_similar_posts(item_id=item_df['hash'].iat[0], model_id="farcaster-v2-similar-items", filter_values={}, items_per_page=5))

# GET POPULAR POSTS
# print(get_popular_posts(model_id = "farcaster-v2-popular-items", 
#                                         filter_values = {},
#                                         # filter_values = {
#                                         #     "item_type": ["post"],
#                                         #     "start_date": "1598919338",
#                                         #     "end_date": "1699524138"
#                                         # }, 
#                                         items_per_page = 5
#                                     ))