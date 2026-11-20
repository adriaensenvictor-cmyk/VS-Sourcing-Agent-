"""Look up release evidence for the campus identity in a scan."""


def releases_for(project, releases):
    # Legacy snapshots and the existing review file key releases by campus name.
    # A separate competition identity can have the same display name.
    if project["id"].startswith("campus:"):
        return releases.get(project["name"], [])
    return []
