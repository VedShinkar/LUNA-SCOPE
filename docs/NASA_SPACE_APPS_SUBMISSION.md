# NASA Space Apps 2026 — Project Submission Draft

This is a copy-ready draft for the NASA Space Apps project page. Confirm all links, product identifiers, team details and the exact build shown to judges before submitting. The project page and linked materials must be in English.

## Project Name

LUNA-SCOPE — Lunar Unified Navigation, Analysis & Site Optimization

## High-Level Project Summary

LUNA-SCOPE is a lunar landing-site exploration and mission-planning platform focused on the Moon's south pole. It brings terrain information, Sun and Earth geometry, solar illumination, communication visibility and mission-level comparison into one interactive workflow. Using NASA lunar data and space-science resources, the prototype helps users examine candidate regions such as Shackleton rim, de Gerlache rim and Malapert Massif, explore operational trade-offs over time, and understand the evidence and uncertainty behind each result. The aim is to make complex landing-site analysis easier to inspect and compare—not to certify a site as safe.

## Link to Project Demo

[ADD PUBLIC LINK TO THE FINAL DEMO VIDEO (30 SECONDS OR LESS) OR A PRESENTATION OF NO MORE THAN 7 SLIDES.]

Before submitting, test the link in a private/incognito browser. It must not require sign-in, permission or registration.

## Link to Final Project

https://github.com/VedShinkar/LUNA-SCOPE

[If a public deployed application is available, add its direct URL here as well. Do not list a local localhost address.]

## Detailed Project Description

Choosing a lunar landing site is a multi-factor problem. A location must be evaluated for its terrain, local horizon, solar access and ability to communicate with Earth. These conditions can vary with location and time, and missing or uncertain data can change how confidently a result should be interpreted.

LUNA-SCOPE brings these considerations into a single exploration workflow. Users can select candidate lunar south-pole regions, inspect terrain information and preliminary hazard indicators, explore Sun/Earth geometry and time-dependent visibility, and compare mission scenarios. Its terrain workflow uses NASA LOLA elevation products to derive and inspect terrain characteristics. The celestial workflow uses SPICE/NAIF and NASA JPL Horizons resources to calculate or examine the geometry of the Sun and Earth as seen from lunar locations. The Operations Timeline brings time-dependent solar and Earth visibility information together, retaining unresolved intervals instead of treating missing information as a positive result.

The Mission Intelligence subsystem provides mission profiles, feasibility checks, weighted scenario comparison and explanatory summaries. The AI Mission Copilot currently uses deterministic natural-language routing to call project tools and present their outputs. It should be described as a tool-integrated assistant, not as a live LLM. Some Mission Intelligence example assessments use synthetic fixtures; these are clearly illustrative and are not validated NASA-derived rankings or landing probabilities.

The prototype is intended to make lunar site analysis more accessible, transparent and reproducible. It can support early exploration and help users identify questions that require deeper engineering analysis. It does not replace detailed mission design, independent scientific validation or formal landing-safety assessment.

Technology used includes Python, geospatial/raster processing, FastAPI, React, TypeScript, browser-based 3D visualization, SPICE/SpiceyPy, NASA JPL Horizons workflows and automated tests.

## Use of Super Intelligence (SI)

Yes. SI tools were used as development assistance during the hackathon. They helped the team with code drafting and debugging, test-writing support, documentation, interface copy and project explanation. The team's problem selection, system design decisions, scientific workflow choices, integration decisions and evaluation of outputs were directed and reviewed by the team.

The current Mission Copilot is deterministic tool routing; it should not be represented as a generative AI model. Any AI-assisted code or generated text/data included in the final project should be identified in the relevant repository documentation or project materials. If generated images or video are included, add the visible SI-generated watermark required by the submission guide. Do not use generated NASA logos, mission identifiers or other NASA branding.

[Edit this disclosure to name the actual SI tools used by the team and the exact assets/code they assisted with. Do not claim image, audio or video generation unless it occurred.]

## NASA Data

- NASA Lunar Orbiter Laser Altimeter (LOLA) regional elevation products distributed through the NASA PDS Geosciences Node / Planetary Geosciences Data (PGDA) resources. The project terrain workflow uses elevation and associated terrain-quality products for the selected study regions. Include the exact product IDs, product page URLs, versions and access dates from the repository's data catalogue/manifest in the final submission.
- NASA/JPL SPICE (NAIF) kernels and toolkit resources used by the celestial-geometry workflow. List the exact kernels and kernel versions actually used in the final build.
- NASA JPL Horizons system used for ephemeris queries and celestial-geometry reference/validation workflows.

Do not list LROC imagery as a data input unless a specific LROC product was actually downloaded and used in the final submitted build. The final page should link to the exact NASA product records, not only to a general NASA homepage.

## Space Agency Partner Data and Other References

- NASA PDS Geosciences Node / PGDA LOLA product documentation and data records.
- NASA/JPL NAIF SPICE documentation and kernel references.
- NASA/JPL Horizons documentation and service.
- Python and geospatial/raster-processing libraries listed in the repository dependency files.
- FastAPI, React and TypeScript documentation and libraries used by the application.
- SpiceyPy documentation.
- GitHub repository and project code: https://github.com/VedShinkar/LUNA-SCOPE

Add exact URLs and versions for all external libraries, datasets, code, images, fonts, icons and other assets that are actually included. Check licences and attribution requirements. Do not claim use of partner-agency datasets unless they were genuinely used.

## Submission checks

- [ ] Project name and summary are final.
- [ ] Demo is either a video of 30 seconds or less OR a slide deck of no more than 7 slides including title/intro.
- [ ] Demo link is public and works in a private browser.
- [ ] Final project link is public and opens without sign-in.
- [ ] Detailed description accurately distinguishes implemented features from planned features.
- [ ] SI tools and their contribution are disclosed accurately.
- [ ] Any SI-generated images/video carry the required visible watermark.
- [ ] NASA data section lists exact products and resource links used.
- [ ] Other references list all actual data, code, text, image and software resources.
- [ ] All required fields are complete and in English.
- [ ] Team has checked originality and submission terms before submitting.
