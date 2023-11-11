#%%
import sqlite3

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('bot_users.db')
cursor = conn.cursor()

# Create a table to store user keypairs (if not already created)
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_keypairs (
    user_id INTEGER PRIMARY KEY,
    public_key TEXT NOT NULL,
    private_key TEXT NOT NULL
)
''')
conn.commit()
#%%

def store_keypair(user_id, public_key, private_key):
    """
    Store a new keypair for a user.
    """
    cursor.execute('''
    INSERT INTO user_keypairs (user_id, public_key, private_key) VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
    public_key=excluded.public_key,
    private_key=excluded.private_key
    ''', (user_id, public_key, private_key))
    conn.commit()

def retrieve_keypair(user_id):
    """
    Retrieve a keypair for a user.
    """
    cursor.execute('SELECT public_key, private_key FROM user_keypairs WHERE user_id=?', (user_id,))
    return cursor.fetchone()

# Example usage:
user_id_example = 123456789  # Replace with actual Telegram user ID
public_key_example = 'user123_public_key'  # Replace with actual public key
private_key_example = 'user123_private_key'  # Replace with actual private key

# Store the keypair
store_keypair(user_id_example, public_key_example, private_key_example)

# Retrieve the keypair
keypair = retrieve_keypair(user_id_example)
if keypair:
    print(f"Public Key: {keypair[0]}")
    print(f"Private Key: {keypair[1]}")
else:
    print("Keypair not found.")

# Close the connection when done
conn.close()

# %%
conn = sqlite3.connect('bot_users.db')
cursor = conn.cursor()

# Create a table to store user keypairs (if not already created)
res = cursor.execute('''
select * from user_keypairss;
''')
res.fetchone()
# %%
