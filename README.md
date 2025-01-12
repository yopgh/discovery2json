# discovery2json

A tool to convert the methods and schemas in a Google discovery document to request and response JSON files, helping with writing request bodies for Google API endpoints with nested schema references more easily.

## Basic usage

Creating request and response JSONs for all endpoints in `people-pa.googleapis.com` in a new directory called `people-pa`:
```
curl 'https://people-pa.googleapis.com/$discovery/rest' > people-pa.json
python3 discovery2json.py people-pa.json people-pa
```

## Directory structure

Discovery2json creates the root directory for all the JSON files as specified in the command-line arguments. It then creates `request.json` and `response.json` files for each method in nested subdirectories matching the endpoint paths. For example, for the `v2/people/updatePhotos` path in `people-pa`, it creates `{root-path}/v2/people/updatePhotos/request.json` and `{root-path}/v2/people/updatePhotos/response.json`.

## JSON format

The output JSONs aren't immediately valid request or response bodies, but should be rather used as alternative documentation to the discovery document. They use strings to document data types and various limitations.

For each method, the script recursively resolves schema references in order to build up the final request and response JSONs. For basic types such as strings and booleans, it uses strings to document the data type. For example, given a property `property` of type `integer`, the corresponding output JSON will be `"property": "<integer>"`. Arrays of a particular data type are expressed as arrays of a single string documenting the data type: `["<integer>"]`. Enum values are expressed as: `"<VALUE1|VALUE2|VALUE3|...>"`.

Many schemas will have several properties, some of which won't be expected or useful for a particular request or won't ever exist in the response. Because we can't know which properties are actually relevant for a given endpoint, all of these may appear in the output JSONs, so it's still your job to figure out what is relevant and what isn't.

## Setting limits

Often, requests will have references to deeply nested schemas with properties that are irrelevant to the endpoint and which can generate large amounts of data. To keep things readable and avoid getting stuck forever generating increasingly nested data, you can set various limits:

### Recursion depth

Use `--request-max-depth` and `--response-max-depth` to set the maximum recursion depth for requests and responses. Data nested beyond the limit is expressed with a string, such as: `"(3 properties hidden: max recursion exceeded)"`. Each has a default value of 100.

### Maximum number of relevant branches

Use `--request-max-branches` and `--response-max-branches` to set the maximum number of properties for a schema. If a schema has more properties than the limit, a documentation string is shown instead, such as: `"(155 properties hidden: max branches exceeded)"`. This is useful for massive schemas used throughout many endpoints that usually hold dozens of properties that we usually don't care about, and keeps the attention on the stuff more specific to the particular endpoint at hand. They both have a default value of 10.

### Start depth for max branches

Use `--request-start-depth` and `--response-start-depth` to decide at what depth the `*-max-branches` arguments come into effect. They have a default value of 1. This is useful as usually we don't want to limit the initial number of objects in the request and response JSONs (depth 0).

### Blacklisting schemas

If you want to completely ignore certain schemas, use `--blacklisted-schemas`, providing a comma-separated list of schema names. For example, you may use `YoutubeApiInnertubeInnerTubeContext,YoutubeApiInnertubeResponseContext` to avoid breaking down the `context` and `responseContext` objects that appear in most YouTube Internal API requests and responses, replacing their values with the documentation string: `"(hidden: blacklisted)"`.

## Getting info for a particular endpoint or group of endpoints

By default, discovery2json generates JSONs for all methods in the discovery document. Sometimes you might want to initially generate all JSONs, only to find a specific, interesting one where the limits from the previous section weren't ideal. In these cases you can generate new JSONs with new arguments just for these endpoints. Sometimes you may want to increase the limits without other endpoints that you don't care about making the script stuck on extremely big schemas. Use the `--regex` argument to ignore endpoints whose paths don't match the regex.

For example, the following will regenerate the updatePhotos JSONs with different arguments from the ones provided earlier:
```
python3 discovery2json.py people-pa.json people-pa --regex updatePhotos --response-max-branches 100
```

`people-pa/people/updatePhotos/response.json` before:
```
{
    "photoToken": "<string>",
    "photoUrl": "<string>",
    "personResponse": {
        "responseStatus": {
            "code": "<integer>",
            "message": "<string>",
            "details": [
                "<object>"
            ]
        },
        "personId": "<string>",
        "person": "(79 properties hidden: max branches exceeded)",
        "debugInfo": "<string>",
        "status": "<string>"
    }
}
```

`people-pa/people/updatePhotos/response.json` after:
```
{
    "photoToken": "<string>",
    "photoUrl": "<string>",
    "personResponse": {
        "responseStatus": {
            "code": "<integer>",
            "message": "<string>",
            "details": [
                "<object>"
            ]
        },
        "personId": "<string>",
        "person": {
            "personId": "<string>",
            "metadata": {
                "model": "<string>",
                "deleted": "<boolean>",
                "contactId": [
                    "<string>"
                ],
                "affinity": [
                    {
                        "affinityType": "<string>",
...
```

## Including description strings

If your discovery document includes non-empty `description` fields with documentation, you can pass `--docs` to include this documentation in the output JSONs. Where possible, this documents objects, arrays, enums, and other basic data types.

Compare the previous `response.json` for `updatePhotos` with the following one, generated with `--docs` using the `staging-people-pa` discovery document (which comes with informative description fields):
```
{
    "__DOCS": "Response from a people get request.",
    "personResponse": [
        "(DOCS: A multimap of results. For successful read of a given `person_id`, there will be one or more entries in this `person_response` list where the `PersonResponse.person_id` matches that of the requested `person_id` and the `PersonResponse.response_status.code` is `0` (which is the value of `util.error.Code.OK`). NOTE: * `PersonResponse.person_id` may not be the same value as the `PersonResponse.person.person_id` (go/people-api-concepts#person-id). * The ordering of entries with the same `PersonResponse.person_id` is not guaranteed and does not indicate a result \"priority\". For unsuccessful reads of a given `person_id`, there will be at least one entry in this `person_response` list where the `PersonResponse.person_id` matches that of the requested `person_id` and the `PersonResponse.response_status.code` is not `0`. *Special Case* Because the InternalPeopleService does not have a dedicated method for reading profile-centric people by Gaia ID, the advised technique is to use GetPeople with a list of Focus-obfuscated Gaia IDs and PROFILE_CENTRIC person model (which is the default if the GetPeopleRequest's merged_person_source_options.person_model_params.person_model is unset). For request meeting that criteria, there will be exactly one entry in the `person_response` list for each requested `person_id`.)",
        {
            "__DOCS": "A single person response entry.",
            "responseStatus": {
                "__DOCS": "The `Status` type defines a logical error model that is suitable for different programming environments, including REST APIs and RPC APIs. It is used by [gRPC](https://github.com/grpc). Each `Status` message contains three pieces of data: error code, error message, and error details. You can find out more about this error model and how to work with it in the [API Design Guide](https://cloud.google.com/apis/design/errors).",
                "code": "<integer: The status code, which should be an enum value of google.rpc.Code.>",
                "message": "<string: A developer-facing error message, which should be in English. Any user-facing error message should be localized and sent in the google.rpc.Status.details field, or localized by the client.>",
                "details": [
                    "(DOCS: A list of messages that carry the error details. There is a common set of message types for APIs to use.)",
                    "<object>"
                ]
            },
            "personId": "<string: The original lookup person ID. This enables the caller to correlate to the original request.>",
            "person": "(79 properties hidden: max branches exceeded)",
            "debugInfo": "<string: Additional useful information for debugging when Status isn't a SUCCESS.>",
            "status": "<string: Deprecated. See the google.rpc.Code 'response_status' field above.>"
        }
    ]
}
```
