<!-- title: Setting up Obsidian for blogging -->
<!-- date: 2024-09-22 -->
<!-- time: 01:44 -->
<!-- draft: no -->

Obsidian is a powerful tool for notetaking. In this post, I will describe how I set it up for blogging on the go.

This site is hosted on Github Pages. Once a push is made to the `main` branch, Github Actions runs a tiny [static site generator](https://github.com/sakibccr/sakibccr.github.io) to convert the markdown files into HTML. So all I needed to do is configure Obsidian to sync with Github. For this, I used the [Obsidian Git](https://github.com/Vinzent03/obsidian-git) plugin. There are a few others that do the same thing. Those should work too.

After that, I thought the source files kind of clutters the view on the sidebar. So I installed [File Hider](https://github.com/Eldritch-Oliver/file-hider), and hidden all the files that are not a blog post.

I also configured the built-in Templates and Daily Notes plugin to create new posts. Now I don't have to insert the dates manually each time I create a new post.

This is the first post using this setup. Once this is done, I will just press _Commit and Sync_ button and this post should be live.

The next step is to take this setup to my mobile phone. Obsidian is available for mobile phones. But I think I will have to use a different plugin for Github sync because the current one seems to be very unstable in Android. I will post about how that goes shortly.
