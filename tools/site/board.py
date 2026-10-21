#!/usr/bin/env python3
# fetch the board's posts (github discussions) into docs/board.json, run by the site workflow
# usage: GITHUB_TOKEN=... tools/site/board.py > docs/board.json
import json, os, sys, urllib.request

REPO = ("tortr-rs", "chamesle")
QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 100, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title createdAt updatedAt upvoteCount body
        author { login avatarUrl }
        category { name slug }
        reactions(content: THUMBS_UP) { totalCount }
        comments(first: 1) { totalCount nodes { body author { login avatarUrl } } }
      }
    }
  }
}"""


def gql(variables):
    req = urllib.request.Request("https://api.github.com/graphql",
                                 data=json.dumps({"query": QUERY, "variables": variables}).encode(),
                                 headers={"Authorization": "bearer " + os.environ["GITHUB_TOKEN"],
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["repository"]["discussions"]


posts, after = [], None
while len(posts) < 500:
    page = gql({"owner": REPO[0], "name": REPO[1], "after": after})
    for d in page["nodes"]:
        author, body = d["author"] or {"login": "ghost", "avatarUrl": ""}, d["body"]
        comments, site = d["comments"]["totalCount"], 0
        # posts made from the website start as a giscus discussion: the real post is its first comment
        if author["login"] == "giscus" and d["comments"]["nodes"]:
            first = d["comments"]["nodes"][0]
            author, body = first["author"] or author, first["body"]
            comments -= 1
            site = 1
        posts.append({
            "n": d["number"], "t": d["title"], "c": d["category"]["slug"],
            "a": author["login"], "av": author["avatarUrl"],
            "at": d["createdAt"], "up": d["updatedAt"],
            "v": d["upvoteCount"] + d["reactions"]["totalCount"],
            "k": comments, "b": body if not site else body[:600], "s": site,
        })
    if not page["pageInfo"]["hasNextPage"]:
        break
    after = page["pageInfo"]["endCursor"]

json.dump(posts, sys.stdout, separators=(",", ":"))
