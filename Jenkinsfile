// Copyright 2019-2021 Hewlett Packard Enterprise Development LP

@Library('dst-shared@master') _

dockerBuildPipeline {
    repository = "cray"
    imagePrefix = "cray"
    app = "ims-load-artifacts"
    name = "ims-load-artifacts"
    description = "Load prebuilt images and recipes into the cray IMS service"
    product = "csm"
    useEntryPointForTest = false
    
    githubPushRepo = "Cray-HPE/ims-load-artifacts"
    /*
        By default all branches are pushed to GitHub

        Optionally, to limit which branches are pushed, add a githubPushBranches regex variable
        Examples:
        githubPushBranches =  /master/ # Only push the master branch
        
        In this case, we push bugfix, feature, hot fix, master, and release branches
    */
    githubPushBranches =  /(bugfix\/.*|feature\/.*|hotfix\/.*|master|release\/.*)/ 
}
