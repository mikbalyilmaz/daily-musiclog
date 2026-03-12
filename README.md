cat << 'EOF' > ~/Desktop/daily-musiclog/README.md
# daily-musiclog

A systematic and chronological archive of daily musical selections, tracking the evolution of auditory aesthetics over time.

## Mathematical Setup

Let $D_1, \dots, D_n$ be a sequence of discrete days.
For each day $D_i$, a singular musical piece $M_i$ is selected.
The repository maintains a continuous mapping $f: D_i \rightarrow M_i$, recording the intersection of time and sound.

## Data Structure

The primary database `daily_tracks.csv` logs the following tuple for each temporal instance:
* `date`: The temporal coordinate ($t$)
* `title`: The nomenclature of the piece and composer
* `url`: The spatial coordinate/routing
* `video_id`: The unique digital identifier

## What the repository renders

As the timeline $n$ increases:
* The `README.md` dynamically displays the current day's selection
* The CSV file acts as a persistent historical ledger, expanding linearly

## Current Selection

<!-- CHOSEN_TODAY:START -->

🎵 [**MFÖ - Gözyaşlarımızı Bitti Mi Sandın (Official Audio)**](https://www.youtube.com/watch?v=_8EWKs4KP9k&list=RD_8EWKs4KP9k&start_radio=1)

<a href="https://www.youtube.com/watch?v=_8EWKs4KP9k&list=RD_8EWKs4KP9k&start_radio=1">
  <img src="https://img.youtube.com/vi/_8EWKs4KP9k/hqdefault.jpg" width="320"/>
</a>

<!-- CHOSEN_TODAY:END -->

## Aesthetic Scope

The curation spans across multiple musical ontologies.

Distributions included:
* Contemporary Classical & Minimalism (Arvo Pärt, György Ligeti)
* Avant-Garde (Krzysztof Penderecki, Olivier Messiaen)
* Eastern Traditional & Maqam (Itrî, Bekir Sıtkı Sezgin)
* World & Jazz (Anouar Brahem, Rabih Abou-Khalil)

These allow comparative observation between:
* tonal vs. atonal structures
* traditional maqam vs. western temperament
* rhythmic complexity vs. ambient stasis

## Update Mechanics

To keep the log stable:
* The `CHOSEN_TODAY` tags in this file act as fixed anchors for programmatic or manual updates
* Historical continuity is preserved strictly within the CSV format
* External dependencies are minimized to ensure long-term archival integrity

## Requirements

Python $\ge$ 3.9

```bash
pip install -r requirements.txt