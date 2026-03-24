import json

with open("analysis/analysis.ipynb", "r") as f:
    nb = json.load(f)

# Update Cell 7 (index 6 is Cell 7 in 0-indexed terms because 0:md, 1:md, 2:code, 3:md, 4:code, 5:md, 6:code)
# Let's dynamically find them based on content to be safe.

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        source = "".join(cell["source"])
        if "Hint: Use collections.Counter on the 'winning_advertiser_id' field" in source:
            cell["source"] = [
                "# Print the total number of records\n",
                "print(f\"Total pipeline records: {len(results)}\")\n",
                "\n",
                "# Compute and print the auction wins per advertiser (overall)\n",
                "print(\"\\nOverall Winners:\")\n",
                "print(df['winning_advertiser_id'].value_counts())\n"
            ]
        elif "# TODO: Find the top winner in the 'sports' category" in source:
            cell["source"] = [
                "# Find the top winner in the 'sports' category\n",
                "sports_df = df[df['content_category'] == 'sports']\n",
                "print(f\"Sports records: {len(sports_df)}\")\n",
                "print(\"\\nSports Winners:\")\n",
                "print(sports_df['winning_advertiser_id'].value_counts())\n"
            ]
    elif cell["cell_type"] == "markdown":
        source = "".join(cell["source"])
        if "**Your Answer (Q1):**" in source:
            cell["source"] = [
                "**Your Answer (Q1):**\n",
                "\n",
                "When I looked at the data, the overall winners were just the advertisers with the biggest bids. This makes sense because they have the most capital. But in the sports category, sportswear started winning a lot more. This happened because of the 1.4x relevance multiplier we put in the code. Even if a sportswear company bid 4.00 and a fast food company bid 5.00, the multiplier pushed the sportswear score to 5.6. This made it the winner. It was cool to see the math actually work to favor relevant ads over just high bidders."
            ]
        elif "**Your Answer (Q2):**" in source:
            cell["source"] = [
                "**Your Answer (Q2):**\n",
                "\n",
                "This was my first time ever cloning a project from a professor and trying to sync it to my own GitHub account. Honestly, just getting the terminal to talk to my account was a huge hurdle. I spent a lot of time just figuring out how to push my code to the right 17862 branch. The most frustrating technical bug was the data types. I did not realize that SQS and DynamoDB handle numbers so differently. My code kept crashing because I was trying to send normal Python floats to a database that requires Decimals. Fixing that taught me that in a distributed system, you cannot just assume things will work like they do in a local script. You have to be super careful about how data moves between different services.\n",
                "\n",
                "Once I got the pipeline actually running, the latency was really high at around 5 seconds. I had to learn how to tune the performance. We realized that by moving the database connection to the very top of the script in the global scope, the Lambda function did not have to reconnect every single time it woke up. We also bumped the memory up to 1024MB. I learned this gives the Lambda a faster CPU for free. Seeing the latency drop from a slow red bar to a green 389ms was the best part of the project. It taught me that building a cloud app is not just about writing the logic. It is about understanding the infrastructure and how to make the hardware work for your code."
            ]

with open("analysis/analysis.ipynb", "w") as f:
    json.dump(nb, f, indent=2)

print("Notebook patched successfully!")
