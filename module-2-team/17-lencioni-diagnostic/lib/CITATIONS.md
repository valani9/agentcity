# Lencioni Five Dysfunctions Diagnostic -- Citations

The Lencioni Five Dysfunctions diagnostic in `vstack.lencioni`
is grounded in seven literature anchors. Each prompt, severity
band, profile pattern, and playbook step traces back to one of
the entries below.

## Primary anchors

1. **Lencioni, P. (2002)** *The Five Dysfunctions of a Team: A
   Leadership Fable.* Jossey-Bass.
   The pyramid model itself -- absence of trust, fear of conflict,
   lack of commitment, avoidance of accountability, inattention to
   results -- with the foundational dependency that lower-tier
   dysfunctions cascade upward.

2. **Lencioni, P. (2005)** *Overcoming the Five Dysfunctions of a
   Team: A Field Guide.* Jossey-Bass.
   Practical interventions per dysfunction. Source for the
   intervention catalogue and the failure-mode playbooks in
   `_playbooks.py`.

## Supporting anchors

3. **Edmondson, A. C. (1999)** "Psychological safety and learning
   behavior in work teams." *Administrative Science Quarterly*,
   44(2), 350-383.
   The foundation tier (absence of trust) is operationalized as
   the absence of psychological safety -- the forensic-mode
   `PsychSafetyAudit` is the Edmondson signal applied to the
   trace.

4. **Hackman, J. R. (2002)** *Leading Teams: Setting the Stage
   for Great Performances.* Harvard Business School Press.
   Team-effectiveness conditions used for the
   `inattention-to-results` dysfunction. Source for the
   "individual optimization" failure mode in `_playbooks.py`.

5. **Salas, E., Reyes, D. L., & McDaniel, S. H. (2018)** "The
   science of teamwork: Progress, reflections, and the road
   ahead." *American Psychologist*, 73(4), 593-600.
   Modern review of team-performance constructs. Used to map
   evidence severity bands and to validate the profile-pattern
   classifier.

6. **Schein, E. H. (1990)** *Organizational Culture and
   Leadership.* Jossey-Bass.
   Source for upstream composition with `vstack.schein_culture`
   -- artifacts, espoused values, and underlying assumptions
   layer below team dynamics.

7. **Wang, Q., Jiang, Y., Liu, Y., Wang, Y., Zhao, X., et al.
   (2023)** "Cooperative LLM Agents: A Survey." *arXiv:2308.00352*.
   The translation layer from human-team theory to multi-agent
   systems. Source for the cascade audit logic and the
   `compose_pattern` intervention type.

## How citations are surfaced

- Every `AttachedPlaybook` carries an `anchor_citation` field.
- The system prompt (`LENCIONI_SYSTEM_PROMPT`) lists the seven
  anchors verbatim so the LLM grounds its scoring in the same
  literature.
- The README's "Why this pattern matters" section cites
  Lencioni (2002, 2005) and Wang et al. (2023) explicitly.

## License & attribution

Citations point to published works owned by their respective
authors and publishers. The `vstack.lencioni` implementation
is a derivative work that applies the Lencioni pyramid to
multi-agent LLM teams; no Lencioni text or Jossey-Bass content
is reproduced here.
