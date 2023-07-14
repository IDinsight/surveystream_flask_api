## [SS-##] <PR Title>

Provide a short, concise and meaningful PR title above. Examples of good PR titles:

- "[#TicketID] Feature: add so-and-so feature"

- "[#TicketID] Fix: fix abc bug"

## Ticket

Fixes: https://idinsight.atlassian.net/browse/SS-##

## Description, Motivation and Context

- What is the goal of the PR?
- What are the changes to achieve that goal?
- Why have you chosen this solution?

## How Has This Been Tested?

## To-do before merge

(Optional -- remove this section if not needed)

Include any notes about things that need to happen before this PR is merged, e.g.:

- [ ] Ensure PR #56 is merged

## Checklist:

This checklist is a useful reminder of small things that can easily be forgotten.
Put an `x` in all the items that apply and remove any items that are not relevant to this PR.

- [ ] My code follows the style guidelines and [standard practices](https://idinsight.atlassian.net/wiki/spaces/DOD/pages/2199912628/Flask+Development+Standards) for this project
- [ ] I have reviewed my own code to ensure good quality
- [ ] I have tested the functionality of my code to ensure it works as intended
- [ ] I have resolved merge conflicts
- [ ] I have written [good commit messages][1]
- [ ] I have scrutinized and edited the migration script with reference to [changes Alembic won't auto-detect](https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect) (if applicable). Note that this includes manually adding the creation of new `CHECK` constraints.
- [ ] I have updated the automated tests (if applicable)
- [ ] I have updated the README file (if applicable)
- [ ] I have updated the OpenAPI documentation (if applicable)

[1]: http://chris.beams.io/posts/git-commit/