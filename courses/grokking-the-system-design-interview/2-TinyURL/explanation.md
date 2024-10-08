# Designing TinyURL

This service will provide short aliases redirecting to long URLs.

Difficulty Level: Easy

## Why do we need URL shortening?

URL shortening is used to create shorter aliases for long URLs, but also to inject analytics and advertising-related routing.
It can also connect a certain end point to device-dependent reroutes that can help ensure correct routing and rendering of webpages for devices.
Finally, you get a more user-friendly, shorter, URL to copy and paste.

## Requirements and Goals of the System

> You should always clarify requirements at the beginning of the interview.
> Be sure to ask questions to find the exact scope of the system that the interview has in mind.

Our URL shortening system should meet the following requirements:

### Functional Requirements

1. Given a URL, our service should generate a shorter and unique alias of it (a short link).
   a. Short link should be easily copied and pasted into applications.
2. When users access a short link, our service should redirect them to the original link.
3. Users should optionally be able to pick a custom short link for their URL.
4. Links will expire after a standard default timespan. Users should be able to specify the expiration time.

### Non-Functional Requirements

1. The system should be highly available. This is required because, if our service is down, all the URL redirections will fail.
2. URL redirection should happen in real-time with minimal latency.
3. Shortened links should not be guessable / predictable.

### Extended Requirements

1. Analytics; e.g., how many times a redirection happened?
2. Our service should also be accessible through REST APIs by other services.

## Capacity Estimation and Constraints

Our system will be read-heavy. There will be lots of redirection requests compared to new URL shortenings. Let's assume a 100:1 ration between read and write.

**_Traffic estimates_** : Assuming we have 500m new NEW URL shortenings per month, with 100:1 read/write ratio, we can expect 50b redirections during the same period:
`100 \* 500M => 50B`

What would be Queries Per Second (QPS) for our system? New URL shortenings per second:
`500m / (30 days * 24 hours * 3600 seconds) = ~200 URLs/second`

**Storage estimates**: Let's assume we store every URL shortening request (and associated shortened link) for 5 years.
Since we expect to have 500M new URLs every month, the total number of objects we expect to store will be 30 billion:
`500m * 5 years * 12 months = 30b`

Let's assume that each stored object will be approximately 500 bytes (just a ballpark estimate -- we will dig into it later). We will need 15TB of total storage:
`30b * 500 bytes = 15TB`

**Bandwidth estimates**: For write requests, since we expect 200 new URLs every second, total incoming data for our service will be 100kb per second:
`200 * 500 bytes = 100 kb/s`

For read requests, since every second we expect ~20k redirections (per the 1:100 ratio), total outgoing data for our service would be 10mb per second:
`20k * 500 bytes = ~10mb/s`

**Memory estimates**: If we want to cache some of the hot URLs that are frequently accessed, how much memory will we need to store them? If we follow the 80-20 rule, meaning 20% of the URLs generate 80% of the traffic, we would like to cache these 20% hot URLs.

Since we have 20k redirections per second, we will be getting 1.7b requests per day:
`20k * 3600 seconds * 24hours = ~1.7b`

To cache these 20% of requests, we will need 170gb of memory at the upper bound (it will be less since the bulk of these redirections will hit repeated links):
`0.2 * 1.7b * 500 bytes = ~170gb`

**High-Level estimates**: Assuming 500m new URLs per month and 100:1 read-write ratio, following is the summary of the high level estimates for our service:

| Types of URLs       | Time estimates |
| ------------------- | -------------- |
| New URLs            | 200/s          |
| URL redirections    | 20k/s          |
| Incoming data       | 100kb/s        |
| Outgoing data       | 10mb/s         |
| Storage for 5 years | 15tb           |
| Memory for cache    | 170gb          |

## System APIs

> Once we've finalized the requirements, it's always a good idea to define the system APIs.
> This should explicitly state what is expected from the system.

We can have SOAP or REST APIs to expose the functionality of our service. Following could be the definitions of the APIs for creating and deleting URLs:

`createURL(api_dev_key, original_url, custom_alias=None, user_name=None, expire_date=None)`
Parameters:
api_dev_key (string): The API developer key of a registered account. This will be used to, among other things, throttle users based on their allocated quota.
original_url (string): Original URL to be shortened.
custom_alias (string): Optional custom key for the URL.
user_name (string): Optional user name to be used in the encoding.
expire_date (string): Optional expiration date for the shortened URL.
Returns: (string)

A successful insertion returns the shortened URL; otherwise, it returns an error code.
deleteURL(api_dev_key, url_key)
Where “url_key” is a string representing the shortened URL to be retrieved; a successful deletion returns ‘URL Removed’.

> Try to signal defensive-programming/guardrail considerations as you see them, leaving them as avenues for further possible exploration, without letting that derail your main thought.

**How do we detect and prevent abuse?** A malicious user can put us out of business by consuming all URL keys in the current design. To prevent abuse, we can limit users via their api_dev_key. Each api_dev_key can be limited to a certain number of URL creations and redirections per some time period (which may be set to a different duration per developer key).

## Database Design

> Defining the DB schema in the early stages of the interview would help to understand the data flow among various components and later would guide towards data partitioning.

A few observations about the nature of the data we will store:

1. We need to store billions of records.
2. Each object we store is small (less than 1kb).
3. There are no relationships between records -- other than storing which user created a URL.
4. Our service is read-heavy.

### Database Schema

We would need two tables: one for storing information about the URL mappings and one for the user's data who created the short link.

### What kind of database should we use?

What kind of database should we use? Since we anticipate storing billions of rows, and we don’t need to use relationships between objects – a NoSQL store like DynamoDB, Cassandra or Riak is a better choice. A NoSQL choice would also be easier to scale. (See resource: SQL vs. NoSQL)

6. Basic System Design and Algorithm

The problem we are solving here is how to generate a short and unique key for a given URL.

In the TinyURL example in Section 1, the shortened URL is “<https://tinyurl.com/rxcsyr3r”>. The last eight characters of this URL constitute the short key we want to generate. We’ll explore two solutions here:
a. Encoding actual URL

We can compute a unique hash (e.g., MD5 or SHA256, etc.) of the given URL. The hash can then be encoded for display. This encoding could be base36 ([a-z ,0-9]) or base62 ([A-Z, a-z, 0-9]) and if we add ‘+’ and ‘/’ we can use Base64 encoding. A reasonable question would be, what should be the length of the short key? 6, 8, or 10 characters?

Using base64 encoding, a 6 letters long key would result in 64^6 = ~68.7 billion possible strings.
Using base64 encoding, an 8 letters long key would result in 64^8 = ~281 trillion possible strings.

With 68.7B unique strings, let’s assume six letter keys would suffice for our system.

If we use the MD5 algorithm as our hash function, it will produce a 128-bit hash value. After base64 encoding, we’ll get a string having more than 21 characters (since each base64 character encodes 6 bits of the hash value). Now we only have space for 6 (or 8) characters per short key; how will we choose our key then? We can take the first 6 (or 8) letters for the key. This could result in key duplication; to resolve that, we can choose some other characters out of the encoding string or swap some characters.

What are the different issues with our solution? We have the following couple of problems with our encoding scheme:

    If multiple users enter the same URL, they can get the same shortened URL, which is not acceptable.
    What if parts of the URL are URL-encoded? e.g., http://www.educative.io/distributed.php?id=design, and http://www.educative.io/distributed.php%3Fid%3Ddesign are identical except for the URL encoding.

Workaround for the issues: We can append an increasing sequence number to each input URL to make it unique and then generate its hash. We don’t need to store this sequence number in the databases, though. Possible problems with this approach could be an ever-increasing sequence number. Can it overflow? Appending an increasing sequence number will also impact the performance of the service.

Another solution could be to append the user id (which should be unique) to the input URL. However, if the user has not signed in, we would have to ask the user to choose a uniqueness key. Even after this, if we have a conflict, we have to keep generating a key until we get a unique one.

b. Generating keys offline

We can have a standalone Key Generation Service (KGS) that generates random six-letter strings beforehand and stores them in a database (let’s call it key-DB). Whenever we want to shorten a URL, we will take one of the already-generated keys and use it. This approach will make things quite simple and fast. Not only are we not encoding the URL, but we won’t have to worry about duplications or collisions. KGS will make sure all the keys inserted into key-DB are unique

Can concurrency cause problems? As soon as a key is used, it should be marked in the database to ensure that it is not used again. If there are multiple servers reading keys concurrently, we might get a scenario where two or more servers try to read the same key from the database. How can we solve this concurrency problem?

Servers can use KGS to read/mark keys in the database. KGS can use two tables to store keys: one for keys that are not used yet, and one for all the used keys. As soon as KGS gives keys to one of the servers, it can move them to the used keys table. KGS can always keep some keys in memory to quickly provide them whenever a server needs them.

For simplicity, as soon as KGS loads some keys in memory, it can move them to the used keys table. This ensures each server gets unique keys. If KGS dies before assigning all the loaded keys to some server, we will be wasting those keys–which could be acceptable, given the huge number of keys we have.

KGS also has to make sure not to give the same key to multiple servers. For that, it must synchronize (or get a lock on) the data structure holding the keys before removing keys from it and giving them to a server.

What would be the key-DB size? With base64 encoding, we can generate 68.7B unique six letters keys. If we need one byte to store one alpha-numeric character, we can store all these keys in:
6 (characters per key) \* 68.7B (unique keys) = 412 GB.

Isn’t KGS a single point of failure? Yes, it is. To solve this, we can have a standby replica of KGS. Whenever the primary server dies, the standby server can take over to generate and provide keys.

Can each app server cache some keys from key-DB? Yes, this can surely speed things up. Although, in this case, if the application server dies before consuming all the keys, we will end up losing those keys. This can be acceptable since we have 68B unique six-letter keys.

How would we perform a key lookup? We can look up the key in our database to get the full URL. If it’s present in the DB, issue an “HTTP 302 Redirect” status back to the browser, passing the stored URL in the “Location” field of the request. If that key is not present in our system, issue an “HTTP 404 Not Found” status or redirect the user back to the homepage.

Should we impose size limits on custom aliases? Our service supports custom aliases. Users can pick any ‘key’ they like, but providing a custom alias is not mandatory. However, it is reasonable (and often desirable) to impose a size limit on a custom alias to ensure we have a consistent URL database. Let’s assume users can specify a maximum of 16 characters per customer key (as reflected in the above database schema).
