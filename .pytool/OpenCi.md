# Edk2 Open Continuous Integration Developling Guideline

Edk2 open CI is the solution to ensure code quality for edk2 repository. Below is the working flow.
![Image text](https://github.com/shenglei10/edk2/blob/OPEN_CI_WIKI/.pytool/Image/edk2OpenCi.png)

## Pipelines

CI solutions in edk2 leverage Pipelines model which is powered by Azure DevOps.
Pipelines is a cloud service that we can use to automatically build and test our
code project and make it available to other users. It can work with Github to test code by
pull request.
![Image text](https://github.com/shenglei10/edk2/blob/OPEN_CI_WIKI/.pytool/Image/Pipelines.png)

To make it easy, a pipeline is a combination of our test steps and project configuration.
In edk2, YAML file is the place to describe a pipeline.

## YAML

YAML file is a file format that can be parsed by Azure DevOps, so that it knows what users
want to do for a project. YAML and YML are the same format. For edk2, we usually use .yml to
create a pipeline like `.azurepipelines/Windows-VS2019.yml` and .yaml to set configuration like
`CryptoPkg/CryptoPkg.ci.yaml` and `.pytool/Plugin/CharEncodingCheck/CharEncodingCheck_plug_in.yaml`.

Note that YAML is powerful and has many features. Full description of its usage can be reached on 
[YAML schema reference](https://docs.microsoft.com/en-us/azure/devops/pipelines/yaml-schema?view=azure-devops&tabs=schema%2Cparameter-schema).


## How to create a pipeline?
For instance, we want to check format issues for patches to be checked into edk2. Then let's
take `.azurepipelines/Ubuntu-PatchCheck.yml` as example.
We should follow below steps to create a pipeline.
![Image text](https://github.com/shenglei10/edk2/blob/OPEN_CI_WIKI/.pytool/Image/YAML.png)
1. Edit Code

	Here we have finished a script `BaseTools/Scripts/PatchCheck.py`. It can check format issues locally.
2. Edit YAML File

	Create a YML file to describe environment and working steps. In `.azurepipelines/Ubuntu-PatchCheck.yml`
	we use Linux(Ubuntu) OS and python37, and call `BaseTools/Scripts/PatchCheck.py` finally.
3. Push to code repo

	When finishing editting code and YAML file locally, users need to push it to Github repository.
	Otherwise, Azure DevOps are not able to find the yml file.
4. Azure Pipelines

	At this stage, we ordinary developers almost finish our job. Beacuse we don't have permission to enable
	the new pipeline for tiano/edk2 in Azure DevOps. We need to contact Michael D Kinney <michael.d.kinney@intel.com>
	or Sean Brogan <sean.brogan@microsoft.com>.
	But if developers want to enable it for our forked edk2. There are some subsquent operations.
	* Sign up for [Azure DevOps](https://azure.microsoft.com/en-us/services/devops/?nav=min).
	* Create a new project with a name whatever we want.
	* Authorize our Github account to Azure DevOps so that it have permission to reach our code.
	* Create a pipeline for a branch of our code base and use the existing yaml in our Github code base(We did it in Push to code repo).
	Here we have done all things for the pipeline.
5. Deploy to target

	Let's test our pipline. Just create a pull request to our target branch and the pipeline will be triggered.
	Test results can be viewed in our pipeline in Azure DevOps.

## Plugin

MicroSoft has created two pipelines for edk2, `Ubuntu-GCC5.yml` and `Windows-VS2019.yml`, which have the same effect
but use different OS. Plugins in `.pytool/Plugin` can be regared as check points for these two piplines. Also, MicroSoft constructed the
infrastructure for these two pipelines, on which plugins run.
The infrastructure consist of two parts, [edk2-pytool-library](https://github.com/tianocore/edk2-pytool-library) and [edk2-pytool-extensions](https://github.com/tianocore/edk2-pytool-extensions). The former one is a library of some basic APIs and the latter one is the library of
some extensive operations, such as parsing arguments, recording logs and so on. It is the combination of the infrastructure and plugins
that describes these two pipelines.

Checking points like GCC build and VS build are implemented as a plugin in `.pytool/Plugin/CompilerPlugin`.
Coding style checking point is implemented in `.pytool/Plugin/EccCheck`. Plugins in edk2 are on equal level and
have their working scope, that they only affect the packages having config files like `CryptoPkg/CryptoPkg.ci.yaml`.
For we developers, in most case we only need to care how to develop plugins.

## How to create a plugin?

Suppose we want to check license issues for each commit. Consequently a new plugin is required. Let's take `.pytool/Plugin/LicenseCheck` as example.
Just like other plugins, we need to:
1. Create a yaml file `.pytool/Plugin/LicenseCheck/LicenseCheck_plug_in.yaml` to describe some basic imformation for this plugin.
2. Create a python file and use the interfacae RunBuildPlugin exposed by the infrastructure to implemente the checking logic. RunBuildPlugin is the entry of a plugin. And this part is the most time consuming job.
3. Create readme for this plugin.
4. Create plugin level section "LicenseCheck" in all package yaml files, to enable some config for the plugin in this package.

## How to run a plugin locally instead of on Azure DevOps?

When developing a plugin, we need to test its performance frequently. And it costs much time to run plugins on Azure DevOps.
So running plugins locally is a good choice. Detail steps can be viewed at [this](https://github.com/tianocore/edk2/tree/master/.pytool#running-ci).
Furthermore, it's strongly recommanded to delete other plugins when test our new plugin. Much time will be saved.

## How to add open ci service for a package?

Maybe we want to extend CI coverage to serve more packages. We need to
* Create a package level config file, `xxxPkg/xxxPkg.ci.yaml`, in which we can set configuration for plugins. And the configuration only works in this package.
* Add the package into `.pytool/CISettings`. This is a python file to set configuration for edk2 open CI, such as working scope and build target.
* Add the package and its build targets into Matrix section in `.azurepipelines/templates/pr-gate-build-job.yml`.

