import json

with open("analysis/analysis.ipynb", "r") as f:
    nb = json.load(f)

# Cell 2 (index 2) contains the %pip install
cell = nb["cells"][2]
source = cell["source"]
source[0] = source[0].replace("boto3", "boto3 pandas")
source[1] = source[1].replace("YOURID", "17862")
cell["source"] = source

# Cell 4 (index 4) contains the exact extraction script
cell = nb["cells"][4]
source = cell["source"]
# Add pandas import
source.insert(1, "import pandas as pd\n")

# Replace last lines with DataFrame load
for i, line in enumerate(source):
    if "if results:" in line:
        source = source[:i]
        source.extend([
            "if results:\n",
            "    df = pd.DataFrame(results)\n",
            "    print(f\"\\nCreated DataFrame with shape: {df.shape}\")\n",
            "    print(\"\\nSample record (first row):\\n\")\n",
            "    print(df.head(1))\n"
        ])
        break

cell["source"] = source

with open("analysis/analysis.ipynb", "w") as f:
    json.dump(nb, f, indent=2)

print("Notebook patched!")
