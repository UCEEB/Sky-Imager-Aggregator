import argparse
from git import Repo


def update(update_mode):
    if update_mode == 'minor' or update_mode == 'main':
        print('Update mode: ' + str(update_mode))
    else:
        return

    if update_mode == 'minor':
        repo = Repo('./')
        origin = repo.remote()

        cli = origin.repo.git
        cli.checkout('origin/master', '.')
        print('Update successful')
    elif update_mode == 'main':
        repo = Repo('./')
        origin = repo.remotes.origin
        origin.fetch()
        origin.fetch('--tags')
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
        cli = origin.repo.git
        cli.checkout(tags[-1], '.')
        print('Update successful')
        print('Current version: ' + str(tags[-1]))


if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser(description='Select update mode: "main" or "minor"')
    parser.add_argument('text', action='store', type=str, help='Select update mode: "main" or "minor"')

    args = parser.parse_args()
    update(args.text)
