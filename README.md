<p>
 <img src="imgs/header.jpg" width="600"/>
 <img src="imgs/af_hegelab.png" width="600"/>
</p>

# AlphaFold

We ([hegelab.org](http://www.hegelab.org)) craeted this fork to remove some bug-like features and implement some new bug-like features. We significantly altered this README.md file to highlight the changes we made. Please read the orgininal one for install instructions at [deepmind alphafold2](https://github.com/deepmind/alphafold). Although we use [AlfaFold without docker @ kalininalab](https://github.com/kalininalab/alphafold_non_docker) for running and testing, our changes should work also in a docker environment.

Till we publish a methodological paper, please read and cite our preprint ["AlphaFold2 transmembrane protein structure prediction shines"](https://www.biorxiv.org/content/10.1101/2021.08.21.457196v1).

# Issues pushed us to contribute

### "Out of Memory"

Some of our AF2 runs with short sequences (~250 a.a.) consumed all of our memory (96GB) and died. Our targets in these cases were highly conserved and produced a very large alignment file, which is read into the memory by a simple .read() in `alphafold/data/tools/jackhmmer.py` ` _query_chunk`. Importantly, the max_hit limit is applied at a later step to the full set, which resides already in the memory, so this option does not prevent this error.
* To overcome this issue exhausting the system RAM, we read the .sto file line-by-line, so only max_hit will reach the memory.
* Since the same data needed line-by-line for a3m conversion, we merged the two step together. We inserted to functions into `alphafold/data/parsers.py`: `get_sto` if only sto is needed and `get_sto_a3m` if also a3m is needed (the code is somewhat redundant but simple and clean).
* This issue was caused by `jackhmmer_uniref90_runner.query` and `jackhmmer_mgnify_runner.query`, so we modified the calls to this function in `alphafold/data/pipeline.py`.
* The called `query` in `alphafold/data/tools/jackhmmer.py` calls `_query_chunk`; from here we call our `get_sto*`; `_query_chunk` returns the `raw_output` dictionary, which also includes 'a3m' as a string or None.

### "ValueError: Cannot create a tensor proto whose content is larger than 2GB."
(https://github.com/deepmind/alphafold/issues/71)
If your protein is highly conserved then the alignment may result in a large data set that does not fit TensorFlow's hard coded 2Gb limit. Theoretically, the call to `jackhmmer_uniref90_result` in `alphafold/data/pipeline.py` should be limited  to `uniref_max_hits: int = 10000`. However, this does not happen. You can find an [easy fix for this at alphafold.hegelab.org](http://alphafold.hegelab.org/) that avoid to use this fork. However, we also fixed other memory problems with the previous fix. So if you use this fork, this "ValueError...2GB" issue is obsolete for you.

# Important notices - from the original README.md file

This package provides an implementation of the inference pipeline of AlphaFold
v2.0. This is a completely new model that was entered in CASP14 and published in
Nature. For simplicity, we refer to this model as AlphaFold throughout the rest
of this document.

Any publication that discloses findings arising from using this source code or
the model parameters should [cite](#citing-this-work) the
[AlphaFold paper](https://doi.org/10.1038/s41586-021-03819-2). Please also refer
to the
[Supplementary Information](https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-021-03819-2/MediaObjects/41586_2021_3819_MOESM1_ESM.pdf)
for a detailed description of the method.

## Citing this work

If you use the code or data in this package, please cite:

```bibtex
@Article{AlphaFold2021,
  author  = {Jumper, John and Evans, Richard and Pritzel, Alexander and Green, Tim and Figurnov, Michael and Ronneberger, Olaf and Tunyasuvunakool, Kathryn and Bates, Russ and {\v{Z}}{\'\i}dek, Augustin and Potapenko, Anna and Bridgland, Alex and Meyer, Clemens and Kohl, Simon A A and Ballard, Andrew J and Cowie, Andrew and Romera-Paredes, Bernardino and Nikolov, Stanislav and Jain, Rishub and Adler, Jonas and Back, Trevor and Petersen, Stig and Reiman, David and Clancy, Ellen and Zielinski, Michal and Steinegger, Martin and Pacholska, Michalina and Berghammer, Tamas and Bodenstein, Sebastian and Silver, David and Vinyals, Oriol and Senior, Andrew W and Kavukcuoglu, Koray and Kohli, Pushmeet and Hassabis, Demis},
  journal = {Nature},
  title   = {Highly accurate protein structure prediction with {AlphaFold}},
  year    = {2021},
  volume  = {596},
  number  = {7873},
  pages   = {583--589},
  doi     = {10.1038/s41586-021-03819-2}
}
`
## License and Disclaimer

This is not an officially supported Google product.

Copyright 2021 DeepMind Technologies Limited.

### AlphaFold Code License

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at https://www.apache.org/licenses/LICENSE-2.0.

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

### Model Parameters License

The AlphaFold parameters are made available for non-commercial use only, under
the terms of the Creative Commons Attribution-NonCommercial 4.0 International
(CC BY-NC 4.0) license. You can find details at:
https://creativecommons.org/licenses/by-nc/4.0/legalcode

### Third-party software

Use of the third-party software, libraries or code referred to in the
[Acknowledgements](#acknowledgements) section above may be governed by separate
terms and conditions or license provisions. Your use of the third-party
software, libraries or code is subject to any such terms and you should check
that you can comply with any applicable restrictions or terms and conditions
before use.

### Mirrored Databases

The following databases have been mirrored by DeepMind, and are available with reference to the following:

*   [BFD](https://bfd.mmseqs.com/) (unmodified), by Steinegger M. and Söding J., available under a [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/).

*   [BFD](https://bfd.mmseqs.com/) (modified), by Steinegger M. and Söding J., modified by DeepMind, available under a [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/). See the Methods section of the [AlphaFold proteome paper](https://www.nature.com/articles/s41586-021-03828-1) for details.

*   [Uniclust30: v2018_08](http://wwwuser.gwdg.de/~compbiol/uniclust/2018_08/) (unmodified), by Mirdita M. et al., available under a [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/).

*   [MGnify: v2018_12](http://ftp.ebi.ac.uk/pub/databases/metagenomics/peptide_database/current_release/README.txt) (unmodified), by Mitchell AL et al., available free of all copyright restrictions and made fully and freely available for both non-commercial and commercial use under [CC0 1.0 Universal (CC0 1.0) Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/).
