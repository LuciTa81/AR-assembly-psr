import { pathToFileURL } from 'node:url';
import fs from 'node:fs/promises';
const root='C:/Users/fresh/Documents/Codex/binocular-slides-20261116';
const skill='C:/Users/fresh/.codex/plugins/cache/openai-primary-runtime/presentations/26.1111.10934/skills/presentations';
const runtime='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1111-574-0_26.1111.574.0_x64__3k8sg7r9htsxt/dependencies';
const {finalizePresentation}=await import(pathToFileURL(skill+'/container_tools/artifact_tool_utils.mjs').href);
await fs.mkdir(root+'/output',{recursive:true});
const result=await finalizePresentation({
  workspaceDir:root,
  candidatePath:root+'/build/validated-candidate.pptx',
  finalPath:root+'/output/AI Assembly Guide_stereo-added_v3.pptx',
  pythonExecutable:runtime+'/python/python.exe',
  integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',
  layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
  explicitTotalSlideCount:19,
  requiredNativeTableOwnerSlides:[],
  requiredNativeChartOwnerSlides:[],
  verifyArtifactToolImport:true,
  receiptPath:root+'/build/validation.json'
});
console.log(JSON.stringify(result));
