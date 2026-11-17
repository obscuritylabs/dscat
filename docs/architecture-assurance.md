# Architecture assurance proposal

## Authority and scope

This candidate supports CAP-01–CAP-05 under the 42 requirements approved in DEC-044. Source: `697a0764bbdaebd6574079720d3841a8241076a3`; authority remains [planning gates](planning-gates.md). [DEC-046](decisions.md#dec-046) records agent first-release architecture readiness and the [risk assessment](architecture-disposition.md); agent implementation-plan readiness, implementation verification and release evidence remain PENDING under [governance](governance.md#required-sdlc-and-approval-gates); DEC-045 supplies standing release delegation. This document owns proposed assurance mechanisms; [requirements](requirements.md) owns acceptance. The [security navigation](canonical-model.md#draft-security-boundaries) points to this authoritative design; later capability details retain their milestone gates.

Mappings: FR-002/010/011 and NFR-002/005/010/013 cover parsing and safe failure; FR-013/014 and NFR-008/020 cover independent states and privacy; NFR-021 covers accessibility; NFR-004/011/012/022 cover secure development. Later capabilities MUST apply these controls when designed; this proposal MUST NOT advance their sequence.

## Threat model and boundaries

Assets are original submissions, canonical snapshots, outputs, publication decisions, build integrity and sensitive metadata. Threat actors include malicious submitters, compromised upstream publishers and accidental operators. Schema validity and filesystem ownership MUST NOT imply publication authority. A compromised host account remains outside this local CLI's protection; filesystem race assumptions MUST be disclosed.

| Boundary / threat | Proposed control | Required negative evidence |
| --- | --- | --- |
| Discovery / path escape and races | Reject symlinks and nonregular inputs, nonrecursive default, reject resolved input/output overlap, check file identity before/after read | Link loops, changed/truncated files, unsafe overlap, lock-file exclusion |
| ZIP / expansion and forged metadata | No disk extraction; preflight and actual streaming counters; reject unsafe/duplicate member names, encryption, multipart ZIP and compression other than stored/deflate | Header/size disagreement, CRC failure, bombs, truncation |
| XML / entities and active content | Disable DTD/entities/XInclude/network; reject document type declarations and unsupported package parts | Entity expansion, external resources, depth limits with network denied |
| Cells / code and formula injection | Reject input formulas including cached results; write user text with explicit string cell type | Formula/cache pairs, leading =/+/-/@, removed validation controls |
| Persistence / corrupt snapshots | Separate complete staging, validated manifests, storage names independent of business IDs | Traversal, serialization/disk/permission/interruption failures preserve previous bytes |
| Projection / nested leakage | Fresh typed allowlisted projection, field/value-specific approval, unknown fields omitted | Nested contacts, locations, URLs, free text, extensions, later lineage |
| Errors / disclosure | Safe typed codes and ordinal source tokens; no raw exception/value/path echo | Hostile filenames, Pydantic input values, XML exception strings |
| Resources / SSRF | Exact bundled transitive schema/context registry; deny unknown references | Offline success and unknown-reference failure with no network attempts |
| Dependencies / substitution and exploitation | Approved sources, age cutoff, frozen lock, hashes, SBOM reconciliation and advisory assessment | Clean frozen install, artifact binding, exploitation/severity release blocks |

The parser MUST reject VBA, macro sheets, ActiveX, OLE/embedded packages, external-link parts, connections and external relationships. An explicit supported package-part matrix MUST be verified using synthetic generator output before parser implementation. Unsupported parts MUST receive fixed diagnostics. Metadata URLs MUST remain inert text; generated workbooks MUST NOT create automatic hyperlink relationships. Generator-authored formulas MAY exist only in designated feedback cells and MUST never supply imported metadata. Runtime references MUST NOT trigger dereferencing.

## Finite resource proposal and measured evidence limitation

Ceilings are inclusive. Actual bytes/elements MUST be counted; advertised sizes alone are insufficient. Exceedance MUST produce `INPUT_LIMIT` with a fixed limit identifier, retry hint and unexamined scope. Initial CLI options MUST NOT bypass ceilings. Files MUST be processed serially in isolated workers; supervisors MUST terminate/reap timed-out workers and continue independent files within invocation limits.

| Resource | Proposed ceiling |
| --- | --- |
| Selected input files | 1,000 per invocation |
| Compressed workbook | 32 MiB |
| ZIP members | 4,096 |
| Actual total uncompressed bytes | 128 MiB |
| Expansion ratio, member and archive | 100:1; denominator max(1, compressed bytes) |
| Individual XML part | 16 MiB |
| XML depth | 64 open elements |
| Worksheets, including hidden | 32 |
| Populated cells, including feedback | 200,000 |
| Text/shared-string length | 32,767 Unicode code points |
| Workbook elapsed processing | 30 seconds, monotonic including preflight |
| Invocation elapsed processing | 300 seconds; remaining inputs unexamined |
| Individual canonical JSON / explicit TOML config | 32 MiB each; JSON depth 64 |
| Invocation actual expanded bytes / snapshot serialized total | 256 MiB each |
| Canonical dataset records | 100,000 |
| Retained diagnostics | 10,000; fixed truncation summary thereafter |
| Coordinator / worker address-space budget | 512 MiB each, one worker at a time; at most 1 GiB combined |

TOOL_VERIFIED preliminary probe, 2026-11-17: Python 3.14.10/Linux processed a synthetic ZIP_STORED worksheet containing 200,000 cells, 5,200,046 XML bytes, 5,200,192 ZIP bytes and depth 5 in 0.472 seconds. Linux process peak RSS was 53,584 KiB. XML SHA-256: `1d9b2bebd19ea983b1ac062a5545edab84f7a4ce63bc450e28cd50d1592e43a3`. This is a standard-library planning experiment, not a secure parser or valid complete XLSX acceptance test. It establishes an initial resource scale only.

Reproduce with `python3` and the following standard-library script:

```python
import hashlib, io, platform, resource, time, zipfile
import xml.etree.ElementTree as ET
start = time.monotonic()
xml = (b'<worksheet><sheetData>' +
       b'<row><c><v>1</v></c></row>' * 200000 +
       b'</sheetData></worksheet>')
archive = io.BytesIO()
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
    z.writestr('xl/worksheets/sheet1.xml', xml)
count = depth = peak = 0
with zipfile.ZipFile(io.BytesIO(archive.getvalue())) as z:
    for event, node in ET.iterparse(z.open(z.infolist()[0]),
                                    events=('start', 'end')):
        if event == 'start':
            depth += 1
            peak = max(peak, depth)
        else:
            if node.tag == 'c':
                count += 1
            node.clear()
            depth -= 1
print(platform.python_version(), platform.system(), count, len(xml),
      len(archive.getvalue()), peak, time.monotonic() - start,
      resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      hashlib.sha256(xml).hexdigest())
```

The research-only hardened Expat/resource experiment retained below measures synthetic boundary structures, ZIP enumeration/reading, streaming byte ceilings, ratio expansion, hostile DTD/entity rejection and actual worker timeout/memory refusal on Linux. Measurements support selection of the proposed ceilings; they MUST NOT count as product parser verification. Resource-specific tests isolate one budget at a time; a structurally accepted fixture MUST still satisfy every budget in the product. Elapsed invocation accounting uses injected monotonic observations at 300 seconds rather than claiming a five-minute end-to-end run. Product implementation MUST wait for architecture disposition and agent implementation-plan readiness. Platform-specific publication/recovery demonstrations remain required acceptance evidence, with concrete tasks/dependencies and blocking conditions established by implementation planning.

## Diagnostic and failure contract

A Pydantic diagnostic MUST contain stable code/severity, invocation-local ordinal `source_token`, OPTIONAL schema-defined sheet/field keys, numeric row/column, target, check state and fixed message key with safe enumerated parameters. Tokens MUST NOT derive from private names or path hashes. Unknown worksheet/field labels MUST NOT echo attacker text. A private source-token association MAY remain in process memory; operators locate sources by deterministic discovery order and ordinal. Duplicate diagnostics MUST identify both tokens.

Renderers MUST omit raw values, Pydantic input payloads, exception strings, archive member names, absolute paths, usernames, URL query strings and arbitrary supplied text. Unexpected exceptions MUST become fixed `INTERNAL_FAILURE`; debug flags MUST NOT bypass minimization. Messages MUST identify expected type/vocabulary/limit and corrective action without quoting content. Human output and JSON reports MUST derive from the same models. Skipped checks MUST be `unperformed`, never passed. Reports MUST NOT count as catalog outputs.

Public export MUST write only approved projection bytes and a minimal public manifest, never full canonical records, configuration or private diagnostic/loss reports. A blocked requested public target MUST withhold the public bundle; internal canonical persistence and partial ready-target behavior MUST follow the core compatibility contract. Invalid intake MUST block all exports by default; target-specific missing facts in otherwise valid intake MUST block only that target. Independent readable inputs MUST continue within limits. Invalid intake and operational/serialization/write failures MUST preserve prior outputs and MUST NOT create a valid publication marker. For otherwise valid intake with an unready requested target, the [compatibility contract](architecture.md#initial-compatibility-contract) permits explicit canonical/successful-target persistence with nonzero status and failed-target assessment; this MUST NOT be reported as successful export of every requested target. Retry after correction MUST NOT accumulate state. The compatibility design owns numeric exit codes; these categories MUST map there without conflicting definitions.

## Independent state and public projection

The canonical model MUST separate validity (`valid`, `invalid`, `unexamined`), optional completeness (missing/present/unknown summary), per-target readiness (`ready`, `blocked`, `unexamined` with missing-fact codes), and metadata review (`not_reviewed`, `in_review`, `approved`, `changes_requested`). Supplied review authority/reference/date MUST be retained. Validator success MUST NOT infer review approval. Missing review MUST NOT invalidate four-field intake.

Access/use and metadata-disclosure determinations MUST separately use unknown/partially restricted/fully restricted/unrestricted, each with supplied authority/reference, rationale, determination date and review status. Publication MUST separately use unknown/approved/denied. Approval MUST bind supplied authority/date to exact field/value projection scope. Inconsistent or missing authority MUST block public readiness; publication MUST NOT imply access rights or legal determination. CLI export MUST only write local artifacts.

Public projection MUST construct fresh target-specific Pydantic DTOs rather than dump canonical models with exclusions. The initial candidate allowlist is identifier, title, description, explicitly selected role-contact label/address and target-required shared catalog fields, each requiring supplied approval of that exact field value. None is intrinsically safe. Record approval MUST NOT authorize every field. Target-required values withheld by policy MUST block public readiness rather than invent placeholders. Ordinary local export and explicitly requested public projection MUST remain distinct.

Recursive rules MUST be closed and versioned: each object path has approved children/values; list members are individually selected by stable identity. Unknown/new children and extension keys MUST stay omitted. Automatic partial-string redaction MUST NOT invent public facts; an alternate value requires supplied approval and canonical preservation of the original. Contacts, locations, URLs, access instructions, free text, semantic references, extensions and later lineage/activity/agent metadata default to omission. Restriction rationale and authority evidence MUST remain private unless independently approved and mapped. Changed values, policy versions, configuration sources or derived mappings MUST invalidate affected approval scopes under the subject bindings below, not timestamps.

Each canonical publication approval MUST be a strict typed object with `subject_kind`, `subject_id`, `target`, `approved_value_sha256`, `policy_version`, `authority` and `approved_on`. `target` MUST be exactly `dcat-us-3` or `odcs-3.2`; authority MUST be supplied nonempty text and date MUST be a strict supplied date. Hashes MUST use lower-case SHA-256 over UTF-8 normalized JSON (sorted keys, compact separators, Unicode NFC text, no NaN/Infinity and no trailing newline). Hashes establish identity only; they MUST NOT establish authentic authority. The closed subject kinds and identifiers MUST be:

| Subject kind | Closed initial subject identifiers and bound values |
| --- | --- |
| `canonical` | `id`, `title`, `description`, `core_party.label`, `core_party.email`, `contract_id`, `contract_version`; each binds the exact normalized scalar in the containing dataset record. No other canonical path is initially public. |
| `configuration` | `dcat_us_3.catalog_id`, `identity.dataset_namespace`, `identity.contract_namespace`, `odcs_3_2.contract_version`, `identity.parties.role_email`; each binds the exact resolved normalized scalar used for the containing record and target. The party email subject MUST additionally bind the normalized core-party label in its hashed value object `{label, role_email}` so another party mapping cannot reuse approval. |
| `derived_target` | `catalog_iri`, `dataset_iri`, `contract_iri`, `contact_email_iri`, `contact_username`, `contract_version`; each binds an object containing the exact normalized emitted value, mapping version, and ordered source subject identifiers with their normalized-value hashes. Unsupported target/subject combinations MUST fail. |

`catalog_iri` MUST apply only to DCAT-US, `contract_iri`, `contact_username` and `contract_version` only to ODCS; `dataset_iri` and `contact_email_iri` MUST apply only to DCAT-US. Source identifiers MUST include every canonical/configuration input to that derivation, including the explicit identity rule and contact-association boolean where used; these dependency inputs MUST be hashed in the derived binding even when not independently emitted. Serializer type/context constants MUST come exclusively from the pinned mapping, never configuration, and MUST be bound through the derived mapping version. Every emitted factual value MUST have its exact applicable canonical or configuration approval and, when transformed/resolved/minted, a derived-target approval. Source approval MUST NOT automatically approve a derived value. A supplied canonical override MUST select canonical approval instead of configuration approval and MUST still require derived approval. Approval entries MUST be unique by `(subject_kind, subject_id, target)` within a record; duplicates/conflicts and unknown subjects MUST fail. Record publication state and applicable disclosure/review controls MUST independently permit projection. Configuration `publication.allowed_subjects` MUST only restrict this closed set; it MUST NOT grant approval, authenticate authority or widen canonical approval.

Resolution MUST occur before approval checking, then hashes MUST be recomputed from actual selected values and mapping dependencies. Missing/stale/malformed approval, changed namespace/catalog identity/resolved contact, changed contact association or identity rule, changed mapping version or changed dependency selection MUST fail closed for the affected public target. These changes MUST NOT rewrite canonical approvals or be automatically reapproved. Planned fixtures MUST include an explicitly approved minimum configuration and derived values yielding both public targets, then separate negative mutations of catalog identity, each namespace, resolved role email/party association, identity rule, mapping version, target and source selection; each MUST withhold the public bundle until fresh supplied exact approvals exist. These are planned product verification cases, not executed architecture research.

Verification MUST inject distinct synthetic sensitive sentinels at every nested field/list/unknown child and assert absence from public bytes and diagnostics. Cases MUST include valid/unreviewed minimum intake, target-blocked valid intake, reviewed/publication-unknown, unauthorized nested child, stale value approval, malformed authority, target-required withholding and new-schema-field exclusion. Target schema/semantic validity MUST be checked after projection; it MUST NOT imply authority to publish. Arbitrary secret detection is not guaranteed; protection depends on explicit approval and allowlists.

## Accessibility criteria and verification arrangements

Selected criteria are labels/instructions, logical navigation/reading order, meaningful headings/links, textual error identification/correction, keyboard operation, visible focus and no reliance on color. WCAG 2.2 criteria 1.3.1, 1.3.2, 1.4.1, 2.1.1, 2.4.3, 2.4.6, 2.4.7, 3.3.1 and 3.3.2 are evaluation references; this selection MUST NOT establish blanket WCAG/legal conformance.

Workbooks MUST put instructions first, use meaningful unique sheet names, simple header rows without merged input cells, logical row/column navigation and field help. Feedback MUST identify errors textually without depending on fills/icons. Protected/hidden feedback MUST NOT trap navigation. Instructions MUST explain keyboard access to optional sections, prompts and corrections. CLI validation MUST cover checks unavailable in Excel independently of formulas.

Selected manual arrangements: Windows 11 with Microsoft Excel for Microsoft 365 desktop and NVDA; Windows Terminal with NVDA for CLI; Microsoft Edge with NVDA for rendered documentation. The implementation plan MUST assign an execution role and concrete environment-acquisition/access dependency for these selected arrangements, with exact OS/build, Excel channel/build, terminal, Edge and NVDA versions recorded before the relevant walkthrough executes. Missing access or versions MUST block that walkthrough and applicable acceptance/release readiness, not plan readiness when the dependency and hard block are explicit. These are selected verification arrangements, not verified portability claims. No selected desktop/assistive environment is available in this shell; manual observations remain PENDING. An identified accessible host MUST execute them; headless or alternate-application inspection MUST NOT substitute for selected Excel evidence.

The walkthrough MUST open a synthetic minimum workbook, navigate required/optional sections without mouse, enter core values, observe dropdowns/prompts, submit missing/invalid/duplicate values, locate/correct errors with a screen reader and repeat without color. CLI checks MUST cover plain redirected output, narrow wrapping and structured reports without ANSI. Documentation checks MUST cover heading/link navigation. Automated checks MUST inspect workbook structure/labels/feedback, no-color output and document semantics. Evidence MUST record observed outcomes, exact environments, limitations and unresolved defects; blockers MUST be corrected before acceptance.

## SSDF and reporting/support design

Final NIST SP 800-218 SSDF 1.1 is the selected baseline in [research](research.md#research-additions-source-evidence); no certification is claimed. The implementation plan MUST assign owners and exact evidence to every practice; task-level nonapplicability MUST have rationale and revisit conditions.

| SSDF practice | Concrete control/evidence |
| --- | --- |
| PO.1 | Approved security requirements, threat model and acceptance mappings |
| PO.2 | Phase ownership, independent verification/review and triage owner |
| PO.3 | Pinned toolchain and reproducible local commands |
| PO.4 | Parser/privacy/security acceptance and release-block criteria |
| PO.5 | Isolated build environments, source/release access and secret exclusion |
| PS.1 | Protected repository workflow, least publication authority, review |
| PS.2 | Source/wheel/sdist bindings, checksums and authenticated retrieval |
| PS.3 | Retained release source/artifacts/SBOM/provenance/advisory dispositions |
| PW.1 | Threat model, offline resources, closed projections |
| PW.2 | Fresh exact-candidate design/security review and dispositions |
| PW.4 | Approved sources, artifact age, lock and dependency advisories |
| PW.5 | Typed boundaries, safe ZIP/XML/path handling, no untrusted evaluation |
| PW.6 | Pinned build configuration, package inspection, frozen verification |
| PW.7 | Ruff/ty, independent review and scope/privacy inspection |
| PW.8 | Hostile-boundary/business-rule/failure-preservation tests |
| PW.9 | Offline runtime, explicit replacement, fail-closed public readiness |
| RV.1 | Private reporting and engineering advisory/exploitation checks |
| RV.2 | Artifact applicability, remediation, severity/exploitation gates, disclosure |
| RV.3 | Root-cause analysis, regression and systemic-control corrections |

Selected reporting route: authenticated issues in the private repository, limited to authorized repository users and contingent on verification that issues are enabled and accessible. Reports MUST be labelled for security triage and MUST omit credentials, real catalog payloads and unnecessary personal information. This route MUST NOT be described as GitHub private vulnerability reporting, an independently private maintainer-only channel, or an anonymous/public reporting service; repository collaborators can read the report. Released `SECURITY.md` plus CLI/docs pointers MUST identify the monitored route, owner, information to submit, sensitive-data avoidance, triage/disclosure process and support policy. An unverified mailbox or public issue route MUST NOT be invented. Private issue access, designated maintainer-role ownership and route exercise are PENDING; failure requires a concrete alternative and blocks release.

Proposed support policy: only the latest published version is supported until its successor releases. Released policy/release notes MUST communicate current support and end of support; the first release MUST state no earlier supported version. This is not a long-term support commitment. Acknowledgment target is five business days; initial triage target is ten business days. Assessment MUST record affected artifacts/versions, severity, known exploitation, reproduction, remediation owner and disclosure constraints; missed targets MUST remain explicit. Disclosure MUST be coordinated with reporter and affected upstream maintainers after a fix or recorded risk-based decision; this design does not authorize automatic public disclosure.

A synthetic report MUST exercise private receipt, acknowledgment, applicability/severity/exploitation assessment, remediation plan, regression evidence, root cause, release assessment and disclosure decision using synthetic information only. Evidence MUST distinguish rehearsal from real reports. Released-source verification MUST confirm reporting/support instructions and artifact/version identity. SBOM/tool pins, advisory sources/freshness and exact release commands belong in later plans; unknown advisory status MUST NOT appear clean.

## Exit evidence

This candidate proposes controls, limits, state/projection rules, selected accessibility arrangements and all SSDF practice mappings. It does not establish product behavior or human approval. The retained synthetic resource experiment supports numeric ceiling selection on the observed Linux environment; product parser verification remains PENDING. The implementation plan MUST assign exact desktop environment recording, publication/recovery and platform resource-adapter verification as concrete owned tasks/dependencies with acceptance/release hard blocks; it MUST NOT claim unexecuted observations. Integrated documentation MUST receive fresh semantic coverage, structural checks and reconciliation. Implementation, tests, local acceptance, remote-main integration, authorized release and downloaded-release verification remain PENDING.

## Resource enforcement and exact package matrix

The supervisor MUST launch one bounded coordinator and one bounded workbook worker; model accumulation MUST stop at invocation expanded-byte, dataset-count and serialized-snapshot ceilings independently of per-file limits. Candidate canonical objects MUST be counted by deterministic serialized length before retention. Global source-token/diagnostic indexes MUST be bounded by file/diagnostic limits. POSIX adapters MUST set hard `RLIMIT_AS` before parsing; Windows MUST use a Job Object process-memory limit and kill-on-job-close. The supervisor MUST check enforcement setup before reading input and fail `RESOURCE_GUARD_UNAVAILABLE` if unavailable. It MUST NOT silently continue unbounded. The Linux experiment demonstrates address-space refusal; macOS and Windows adapter verification remains an explicitly planned product-verification task and acceptance/release condition, not a completed portability claim. Per-process caps bound the selected serial topology to at most 1 GiB address space; they MUST NOT be described as exact resident-memory usage.

The supported XLSX part-name matrix MUST be closed: `[Content_Types].xml`, `_rels/.rels`, `docProps/core.xml`, `docProps/app.xml`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, `xl/styles.xml`, OPTIONAL `xl/sharedStrings.xml`, OPTIONAL `xl/theme/theme1.xml`, and `xl/worksheets/sheetN.xml` where N is a positive decimal sheet index. Directory entries MAY exist only as parents of these paths. All other parts MUST fail. Relationship types MUST be limited to officeDocument, core-properties, extended-properties, worksheet, styles, sharedStrings and theme using the supported OOXML transitional namespaces. Relationship targets MUST resolve within these exact paths, MUST NOT be external, and MUST NOT contain traversal, URI schemes, backslashes or absolute paths. Worksheet relationships/drawings/comments/tables/calcChain/custom properties MUST NOT be emitted or accepted in schema 1.0; intake tables are ordinary worksheet ranges rather than OOXML table parts. Unknown MIME content types, relationship namespaces and parts MUST fail with `UNSUPPORTED_WORKBOOK_PART`. Ordinary unrelated worksheet ranges MAY be ignored semantically after security validation; this does not allow unknown package parts. The implementation plan MUST verify the generator produces this matrix, not silently widen it for library defaults.

## Retained resource selection experiment

TOOL_VERIFIED, 2026-11-17: source `697a0764bbdaebd6574079720d3841a8241076a3`, planning-only dirty candidate; Linux/Python 3.14.10. The following temporary research script completed successfully with all assertions passing using `python3 /tmp/dscat-resource-probe.py > /tmp/dscat-resource-probe.jsonl`. The script is retained as evidence here, not shipped product code. Recreate it verbatim in a temporary file to reproduce. SHA-256 of script bytes: `d90c89bb25fcaee0d6925214dd4f2feba80f5badd43f4b7f13914d0b05fb09bf`; result bytes: `66d87a4c048cf2f20c3cfe9dc99999627ec73783a4a977b0057fc6762e6d2684`. RSS values are Linux KiB process high-water observations, not per-fixture deltas. Individual dimensions are isolated; actual ZIP expansion ignores the ratio guard only for measuring its own byte ceiling. The 100:1 exact boundary uses a synthetic compressed-byte denominator, while the real deflate bomb separately demonstrates actual compressed-stream expansion refusal. File, record and diagnostic counts use actual temporary directory enumeration or allocated collections. Clock injection validates invocation accounting; actual 30-second process timeout independently demonstrates termination and reaping. These results support finite architecture limits, not product conformance or other operating-system verification.

```python
import io,json,os,resource,subprocess,sys,tempfile,time,zipfile,zlib
from xml.parsers import expat
M=1024*1024
LIMITS={'members':4096,'depth':64,'text':32767,'cells':200000,'sheets':32,'compressed':32*M,'expanded':128*M,'xml':16*M,'json_bytes':32*M,'files':1000,'diagnostics':10000,'invocation_expanded':256*M,'snapshot':256*M,'datasets':100000}
class Limit(Exception):pass
def cap(n,k):
 if n>LIMITS[k]:raise Limit(k)
def parse(raw,**changes):
 limits=LIMITS|changes;p=expat.ParserCreate();depth=cells=text=0
 def start(name,attrs):
  nonlocal depth,cells,text
  depth+=1;text=0
  if depth>limits['depth']:raise Limit('depth')
  if name=='c':
   cells+=1
   if cells>limits['cells']:raise Limit('cells')
 def end(name):
  nonlocal depth,text
  depth-=1;text=0
 def chars(value):
  nonlocal text
  text+=len(value)
  if text>limits['text']:raise Limit('text')
 def forbidden(*a):raise Limit('unsafe_xml')
 p.StartElementHandler=start;p.EndElementHandler=end;p.CharacterDataHandler=chars
 p.StartDoctypeDeclHandler=forbidden;p.EntityDeclHandler=forbidden;p.ExternalEntityRefHandler=forbidden
 for offset in range(0,len(raw),65536):p.Parse(raw[offset:offset+65536],False)
 p.Parse(b'',True)
def expect(label,fn,reject):
 t=time.monotonic()
 try:fn();actual=False
 except Limit:actual=True
 assert actual==reject,(label,actual,reject)
 print(json.dumps({'case':label,'result':'reject' if actual else 'accept','seconds':round(time.monotonic()-t,4),'rss_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)
def archive(n):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  for i in range(n):z.writestr(f'xl/worksheets/sheet{i}.xml',b'<s/>')
 return b.getvalue()
def zipcount(n,key):
 with zipfile.ZipFile(io.BytesIO(archive(n))) as z:cap(len(z.infolist()),key)
def bytes_stream(n,key):
 total=0
 for offset in range(0,n,65536):
  data=b'x'*min(65536,n-offset);total+=len(data);cap(total,key)
def compressed_stream(n):
 # Stored ZIP payload; actual member bytes and container bytes count separately.
 with tempfile.TemporaryFile() as f:
  with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_STORED) as z:
   with z.open('payload','w') as out:
    for offset in range(0,n,65536):out.write(b'x'*min(65536,n-offset))
  f.seek(0);total=0
  while data:=f.read(65536):total+=len(data);cap(total,'compressed')
def ratio(raw_n,comp_n):
 raw=b'a'*raw_n;packed=zlib.compress(raw)
 # ZIP_STORED padding models exact advertised/actual denominator independently.
 denominator=max(len(packed),comp_n,1)
 expanded=0;d=zlib.decompressobj()
 for offset in range(0,len(packed),128):
  expanded+=len(d.decompress(packed[offset:offset+128],128*M+1))
  if expanded>100*denominator:raise Limit('ratio')
for key,fn in [('depth',lambda n:parse(b'<a>'*n+b'</a>'*n)),('text',lambda n:parse(b'<a>'+b'x'*n+b'</a>')),('cells',lambda n:parse(b'<s>'+b'<c/>'*n+b'</s>')),('members',lambda n:zipcount(n,'members')),('sheets',lambda n:zipcount(n,'sheets'))]:
 for delta in (0,1):expect(f'{key}:{LIMITS[key]+delta}',lambda n=LIMITS[key]+delta,fn=fn:fn(n),bool(delta))
for key in ('expanded','xml','json_bytes','invocation_expanded','snapshot'):
 for delta in (0,1):expect(f'{key}:{LIMITS[key]+delta}',lambda n=LIMITS[key]+delta,k=key:bytes_stream(n,k),bool(delta))
# ZIP_STORED overhead is 112 bytes for the selected single member name.
for delta in (0,1):expect(f'compressed:{32*M+delta}',lambda d=delta:compressed_stream(32*M-112+d),bool(delta))
for delta in (0,1):expect(f'ratio:{100000+delta}/1000',lambda d=delta:ratio(100000+d,1000),bool(delta))
def bomb():
 packed=zlib.compress(b'x'*(1024*1024));d=zlib.decompressobj();expanded=0
 for offset in range(0,len(packed),128):
  expanded+=len(d.decompress(packed[offset:offset+128],65536))
  if expanded>100*len(packed):raise Limit('ratio')
expect('actual-deflate-bomb',bomb,True)
def expanded_archive(n):
 with tempfile.TemporaryFile() as f:
  with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED) as z:
   with z.open('payload','w') as out:
    for offset in range(0,n,65536):out.write(b'x'*min(65536,n-offset))
  f.seek(0)
  with zipfile.ZipFile(f) as z:
   with z.open('payload') as member:
    total=0
    while data:=member.read(65536):total+=len(data);cap(total,'expanded')
for delta in (0,1):expect('actual-zip-expanded:'+str(128*M+delta),lambda d=delta:expanded_archive(128*M+d),bool(delta))
for payload in (b'<!DOCTYPE a [<!ENTITY e "x">]><a>&e;</a>',b'<!DOCTYPE a SYSTEM "https://invalid.example/a"><a/>'):
 expect('unsafe_xml',lambda p=payload:parse(p),True)
with tempfile.TemporaryDirectory() as root:
 for i in range(1001):
  open(os.path.join(root,str(i)+'.xlsx'),'wb').close()
  if i>=999:expect('files:'+str(i+1),lambda:cap(sum(1 for _ in os.scandir(root)),'files'),i==1000)
for delta in (0,1):expect('datasets:'+str(100000+delta),lambda d=delta:cap(len([None]*(100000+d)),'datasets'),bool(delta))
for delta in (0,1):expect('diagnostics:'+str(10000+delta),lambda d=delta:cap(len([None]*(10000+d)),'diagnostics'),bool(delta))
for limit in (30,300):
 # Injected monotonic observations exercise scheduling without a 300-second wait.
 for delta in (0,0.001):
  def elapsed(l=limit,d=delta):
   if l+d>l:raise Limit('elapsed')
  expect(f'monotonic-accounting:{limit}+{delta}',elapsed,bool(delta))
t=time.monotonic();p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
try:p.wait(timeout=30);raise AssertionError('worker did not time out')
except subprocess.TimeoutExpired:p.kill();p.wait()
assert p.returncode<0
print(json.dumps({'case':'actual-worker-timeout','seconds':round(time.monotonic()-t,3),'returncode':p.returncode}),flush=True)
child='import resource;resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));a=bytearray(600*1024**2)'
p=subprocess.run([sys.executable,'-c',child],capture_output=True)
assert p.returncode!=0 and b'MemoryError' in p.stderr
print(json.dumps({'case':'worker-memory-512MiB','result':'allocation-refused','returncode':p.returncode}),flush=True)
```

Observed output:

```jsonl
{"case": "depth:64", "result": "accept", "seconds": 0.0, "rss_KiB": 21120}
{"case": "depth:65", "result": "reject", "seconds": 0.0, "rss_KiB": 21120}
{"case": "text:32767", "result": "accept", "seconds": 0.0, "rss_KiB": 21120}
{"case": "text:32768", "result": "reject", "seconds": 0.0, "rss_KiB": 21120}
{"case": "cells:200000", "result": "accept", "seconds": 0.0525, "rss_KiB": 22144}
{"case": "cells:200001", "result": "reject", "seconds": 0.0527, "rss_KiB": 23088}
{"case": "members:4096", "result": "accept", "seconds": 0.0367, "rss_KiB": 23088}
{"case": "members:4097", "result": "reject", "seconds": 0.0333, "rss_KiB": 23968}
{"case": "sheets:32", "result": "accept", "seconds": 0.0003, "rss_KiB": 23968}
{"case": "sheets:33", "result": "reject", "seconds": 0.0003, "rss_KiB": 23968}
{"case": "expanded:134217728", "result": "accept", "seconds": 0.0018, "rss_KiB": 23968}
{"case": "expanded:134217729", "result": "reject", "seconds": 0.0019, "rss_KiB": 23968}
{"case": "xml:16777216", "result": "accept", "seconds": 0.0003, "rss_KiB": 23968}
{"case": "xml:16777217", "result": "reject", "seconds": 0.0003, "rss_KiB": 23968}
{"case": "json_bytes:33554432", "result": "accept", "seconds": 0.0005, "rss_KiB": 23968}
{"case": "json_bytes:33554433", "result": "reject", "seconds": 0.0005, "rss_KiB": 23968}
{"case": "invocation_expanded:268435456", "result": "accept", "seconds": 0.004, "rss_KiB": 23968}
{"case": "invocation_expanded:268435457", "result": "reject", "seconds": 0.0041, "rss_KiB": 23968}
{"case": "snapshot:268435456", "result": "accept", "seconds": 0.004, "rss_KiB": 23968}
{"case": "snapshot:268435457", "result": "reject", "seconds": 0.004, "rss_KiB": 23968}
{"case": "compressed:33554432", "result": "accept", "seconds": 0.0197, "rss_KiB": 23968}
{"case": "compressed:33554433", "result": "reject", "seconds": 0.0164, "rss_KiB": 23968}
{"case": "ratio:100000/1000", "result": "accept", "seconds": 0.0005, "rss_KiB": 23968}
{"case": "ratio:100001/1000", "result": "reject", "seconds": 0.0005, "rss_KiB": 23968}
{"case": "actual-deflate-bomb", "result": "reject", "seconds": 0.0029, "rss_KiB": 24480}
{"case": "actual-zip-expanded:134217728", "result": "accept", "seconds": 0.5783, "rss_KiB": 24480}
{"case": "actual-zip-expanded:134217729", "result": "reject", "seconds": 0.5971, "rss_KiB": 24480}
{"case": "unsafe_xml", "result": "reject", "seconds": 0.0, "rss_KiB": 24480}
{"case": "unsafe_xml", "result": "reject", "seconds": 0.0, "rss_KiB": 24480}
{"case": "files:1000", "result": "accept", "seconds": 0.0003, "rss_KiB": 24480}
{"case": "files:1001", "result": "reject", "seconds": 0.0002, "rss_KiB": 24480}
{"case": "datasets:100000", "result": "accept", "seconds": 0.0001, "rss_KiB": 24480}
{"case": "datasets:100001", "result": "reject", "seconds": 0.0001, "rss_KiB": 24480}
{"case": "diagnostics:10000", "result": "accept", "seconds": 0.0, "rss_KiB": 24480}
{"case": "diagnostics:10001", "result": "reject", "seconds": 0.0, "rss_KiB": 24480}
{"case": "monotonic-accounting:30+0", "result": "accept", "seconds": 0.0, "rss_KiB": 24480}
{"case": "monotonic-accounting:30+0.001", "result": "reject", "seconds": 0.0, "rss_KiB": 24480}
{"case": "monotonic-accounting:300+0", "result": "accept", "seconds": 0.0, "rss_KiB": 24480}
{"case": "monotonic-accounting:300+0.001", "result": "reject", "seconds": 0.0, "rss_KiB": 24480}
{"case": "actual-worker-timeout", "seconds": 30.012, "returncode": -9}
{"case": "worker-memory-512MiB", "result": "allocation-refused", "returncode": 1}
```
