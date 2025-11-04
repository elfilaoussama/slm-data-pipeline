#!/usr/bin/env bash
set -euo pipefail

# Launch the large multi-query discovery with your exact parameters.
# Note: This can take a while depending on rate limits and subquery fan-out.

PY=python3
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
fi

"$PY" pipeline.py \
  --allowed-licenses "MIT,Apache-2.0,BSD-3-Clause" \
  --languages python \
  --min-stars 100 \
  --max-repos 500 \
  --keyword-query 'graph OR "graph algorithms" OR dijkstra | bfs OR dfs OR "shortest path" | "minimum spanning tree" OR mst OR "linked list" | stack OR queue OR tree | trie OR heap OR hashmap | "hash table" OR "dynamic programming" OR "recursion" | "sorting algorithms" OR "search algorithms" OR "big o notation" | "machine learning" OR sklearn OR pytorch | tensorflow OR "training script" OR "model training" | "deep learning" OR "neural network" OR "convolutional" | "reinforcement learning" OR "genai" OR "generative ai" | "LLM" OR "RAG" OR "fine-tuning" | nlp OR tokenization OR spacy | nltk OR transformers OR bert | "text classification" OR "named entity" OR "sentiment analysis" | "word embedding" OR "topic modeling" OR "seq2seq" | opencv OR "computer vision" OR "object detection" | "image segmentation" OR "image recognition" OR "pose estimation" | yolo OR "feature detection" OR "image processing" | "data analysis" OR numpy OR pandas | scipy OR "jupyter notebook" OR "data science" | matplotlib OR seaborn OR plotly | d3.js OR "data visualization" | "web scraping" OR beautifulsoup OR selenium | requests OR scraper OR crawler | scrapy OR "headless browser" OR "data extraction" | "REST API" OR GraphQL OR "web server" | "node.js" OR express OR nestjs | django OR flask OR fastapi | "ruby on rails" OR "spring boot" OR java | nginx OR "api gateway" OR microservices | javascript OR typescript OR react | vue OR angular OR svelte | "tailwind css" OR "styled-components" OR "web component" | next.js OR "three.js" OR "webgl" | sql OR sqlalchemy OR postgres | sqlite OR "mysql" OR "mariadb" | orm OR "database design" OR "data modeling" | "NoSQL" OR mongodb OR redis | cassandra OR "database migration" | "data pipeline" OR "ETL" OR "apache airflow" | "apache spark" OR "apache kafka" OR "data warehouse" | hadoop OR "big data" OR "streaming data" | docker OR kubernetes OR terraform | ansible OR "infrastructure as code" OR "IaC" | "github actions" OR "CI/CD" OR jenkins | "prometheus" OR "grafana" OR "monitoring" | "service mesh" OR "istio" OR "linkerd" | pytest OR "unit test" OR "integration test" | "e2e test" OR jest OR cypress | "test automation" OR "behavior driven" OR cucumber | cli OR click OR argparse | "command line" OR "shell script" OR bash | rust OR go OR golang | "c++" OR "systems programming" OR "kernel" | crypto OR encryption OR hashing | "penetration testing" OR "pentest" OR "malware analysis" | "reverse engineering" OR "cybersecurity" OR "vulnerability" | "exploit" OR "burp suite" OR "network security" | "react native" OR "flutter" OR "swift" | "swiftui" OR kotlin OR "jetpack compose" | "android dev" OR "ios dev" OR "cross-platform" | "game dev" OR "game engine" OR unity | unreal OR godot OR "2d game" | "3d game" OR "game shader" OR "opengl" | blockchain OR "smart contract" OR solidity | ethereum OR "web3" OR "decentralized" | hardhat OR truffle OR "dapp" | "design system" OR "ui design" OR "ux design" | figma OR "user interface" OR "user experience"' \
  --min-function-loc 4 \
  --max-function-loc 400 \
  --quality-min-loc 6 \
  --quality-max-loc 400 \
  --quality-max-cyclomatic 15 \
  --quality-max-nesting 5 \
  --quality-allow-synthetic-docs \
  --dedup-shingle-size 8 \
  --minhash-perms 96
